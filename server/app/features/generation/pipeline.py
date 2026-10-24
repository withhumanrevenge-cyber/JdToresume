"""Application-pack pipeline (ARCHITECTURE §4): a fixed DAG in code; the LLM fills in each step's schema.

    (jd_extract) ─► match_plan ─┬─► resume_tailor ─► lint + verify ─► (revise ×≤1) ─► lint ─► "resume"
                                ├─► cover_letter ─► lint ─────────────────────────────────► "cover_letter"
                                └─► outreach ─► lint ─────────────────────────────────────► "outreach"

`stream_pack` is the one orchestrator. It yields each piece the moment it's ready, which is what the API streams
to the browser. `generate_pack` collects the same stream into a `PackResult` for the eval harness and CLI.
Match runs before the fan-out so the shared prefix (system policy + profile) is cached for the parallel steps.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass
from typing import Literal

from pydantic import BaseModel

from app.llm.client import GroqLLM, LLMCall
from app.llm.pii import redact_profile
from app.llm.router import Mode, step_config
from app.llm.schemas import (
    CareerProfile, ContactDetails, CoverLetter, JobSpec, MatchReport, OutreachPack, TailoredResume, VerifyReport,
)
from app.llm.style.linters import Finding, lint_cover_letter, lint_outreach, lint_resume

PieceKind = Literal["job", "match_report", "resume", "cover_letter", "outreach"]


# --------------------------------------------------------------------------- what each piece contains

class LintFinding(BaseModel):
    """A deterministic check that flagged something (app/llm/style/linters.py)."""

    check: str
    location: str
    message: str
    severity: str


class ResumeOutcome(BaseModel):
    resume: TailoredResume  # the final version
    revised: bool
    verify: VerifyReport  # the reviewer's findings on the first draft
    findings: list[LintFinding]  # deterministic checks on the final version
    draft: TailoredResume | None  # the first draft, kept only when it was revised (for audits and evals)
    draft_findings: list[LintFinding]


class CoverLetterOutcome(BaseModel):
    letter: CoverLetter
    findings: list[LintFinding]


class OutreachOutcome(BaseModel):
    outreach: OutreachPack
    findings: list[LintFinding]


@dataclass(frozen=True)
class Piece:
    kind: PieceKind
    content: BaseModel


# --------------------------------------------------------------------------- the orchestrator

async def stream_pack(
    llm: GroqLLM,
    profile: CareerProfile,
    contact: ContactDetails,
    *,
    job: JobSpec | None = None,
    jd_text: str | None = None,
    mode: Mode = "deep",
    model_override: str | None = None,
) -> AsyncIterator[Piece]:
    """Yield the pack piece by piece. Pass a parsed `job`, or `jd_text` to have it extracted first."""

    def cfg(step: str):
        return step_config(step, mode, model_override)

    # The LLM sees a redacted view of the profile; the PII guard in run_step still checks every request.
    prefix = [("career_profile", redact_profile(profile, contact))]

    if job is None:
        if not jd_text:
            raise ValueError("stream_pack needs either a parsed job or the job description text")
        job = await llm.run_step("jd_extract", output=JobSpec, cfg=cfg("jd_extract"),
                                 blocks=[("job_description", jd_text)], contact=contact)
        yield Piece("job", job)

    match = await llm.run_step("match_plan", output=MatchReport, cfg=cfg("match_plan"),
                               prefix_blocks=prefix, blocks=[("job_spec", job)], contact=contact)
    yield Piece("match_report", match)

    shared = [("job_spec", job), ("match_report", match)]

    async def resume() -> ResumeOutcome:
        draft = await llm.run_step("resume_tailor", output=TailoredResume, cfg=cfg("resume_tailor"),
                                   prefix_blocks=prefix, blocks=shared, contact=contact)
        draft_findings = lint_resume(draft, profile)
        verify = await llm.run_step("verify", output=VerifyReport, cfg=cfg("verify"), prefix_blocks=prefix,
                                    blocks=[("job_spec", job), ("tailored_resume", draft)], contact=contact)
        if not _needs_revision(verify, draft_findings):
            return ResumeOutcome(resume=draft, revised=False, verify=verify, findings=_out(draft_findings),
                                 draft=None, draft_findings=[])
        final = await llm.run_step(
            "revise", output=TailoredResume, cfg=cfg("revise"), prefix_blocks=prefix,
            blocks=[*shared, ("tailored_resume", draft), ("violations", _problems(verify, draft_findings))],
            contact=contact,
        )
        return ResumeOutcome(resume=final, revised=True, verify=verify, findings=_out(lint_resume(final, profile)),
                             draft=draft, draft_findings=_out(draft_findings))

    async def cover_letter() -> CoverLetterOutcome:
        letter = await llm.run_step("cover_letter", output=CoverLetter, cfg=cfg("cover_letter"),
                                    prefix_blocks=prefix, blocks=shared, contact=contact)
        return CoverLetterOutcome(letter=letter, findings=_out(lint_cover_letter(letter, profile)))

    async def outreach() -> OutreachOutcome:
        pack = await llm.run_step("outreach", output=OutreachPack, cfg=cfg("outreach"),
                                  prefix_blocks=prefix, blocks=shared, contact=contact)
        return OutreachOutcome(outreach=pack, findings=_out(lint_outreach(pack)))

    # The three pieces run in parallel; each is handed over as soon as it finishes.
    running: dict[asyncio.Task, PieceKind] = {
        asyncio.create_task(resume()): "resume",
        asyncio.create_task(cover_letter()): "cover_letter",
        asyncio.create_task(outreach()): "outreach",
    }
    try:
        while running:
            finished, _ = await asyncio.wait(running, return_when=asyncio.FIRST_COMPLETED)
            for task in finished:
                kind = running.pop(task)
                yield Piece(kind, task.result())  # re-raises the step's error, if it failed
    finally:
        # If the caller stops early (client disconnected, or a step failed), don't leave AI calls running.
        for task in running:
            task.cancel()
        await asyncio.gather(*running, return_exceptions=True)


def _needs_revision(verify: VerifyReport, findings: list[Finding]) -> bool:
    return any(v.severity in ("high", "medium") for v in verify.violations) or any(
        f.severity in ("high", "medium") for f in findings
    )


def _problems(verify: VerifyReport, findings: list[Finding]) -> list[dict]:
    """What the reviser is asked to fix: the reviewer's and the linters' high and medium findings."""
    problems = [v.model_dump() for v in verify.violations if v.severity in ("high", "medium")]
    problems += [{"location": f.location, "kind": f.check, "explanation": f.message, "severity": f.severity}
                 for f in findings if f.severity in ("high", "medium")]
    return problems


def _out(findings: list[Finding]) -> list[LintFinding]:
    return [LintFinding(**asdict(f)) for f in findings]


# --------------------------------------------------------------------------- the whole pack at once (evals, CLI)

class PackResult(BaseModel):
    mode: str
    model_override: str | None
    job: JobSpec
    match: MatchReport
    resume_initial: TailoredResume
    resume: TailoredResume
    revised: bool
    verify: VerifyReport
    lint_initial: list[dict]
    lint_final: list[dict]
    cover_letter: CoverLetter
    cover_letter_lint: list[dict]
    outreach: OutreachPack
    outreach_lint: list[dict]
    calls: list[LLMCall]
    wall_ms: int


async def generate_pack(
    llm: GroqLLM,
    profile: CareerProfile,
    contact: ContactDetails,
    jd_text: str,
    *,
    mode: Mode = "deep",
    model_override: str | None = None,
) -> PackResult:
    started = time.perf_counter()
    first_call = len(llm.calls)
    pieces = {piece.kind: piece.content async for piece in
              stream_pack(llm, profile, contact, jd_text=jd_text, mode=mode, model_override=model_override)}
    resume: ResumeOutcome = pieces["resume"]  # type: ignore[assignment]
    letter: CoverLetterOutcome = pieces["cover_letter"]  # type: ignore[assignment]
    outreach: OutreachOutcome = pieces["outreach"]  # type: ignore[assignment]

    def dicts(findings: list[LintFinding]) -> list[dict]:
        return [f.model_dump() for f in findings]

    return PackResult(
        mode=mode, model_override=model_override, job=pieces["job"], match=pieces["match_report"],
        resume_initial=resume.draft or resume.resume, resume=resume.resume, revised=resume.revised,
        verify=resume.verify,
        lint_initial=dicts(resume.draft_findings if resume.revised else resume.findings),
        lint_final=dicts(resume.findings),
        cover_letter=letter.letter, cover_letter_lint=dicts(letter.findings),
        outreach=outreach.outreach, outreach_lint=dicts(outreach.findings),
        calls=llm.calls[first_call:], wall_ms=int((time.perf_counter() - started) * 1000),
    )
