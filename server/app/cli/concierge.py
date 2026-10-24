"""Phase 0 concierge tool (docs/phase0/concierge-playbook.md). Real users' data stays in ./concierge/ (gitignored).

  .venv/Scripts/python.exe -m app.cli.concierge parse --user priya resume.pdf
      -> concierge/priya/profile.json + contact.json  (REVIEW AND EDIT THESE WITH THE USER before generating)
  .venv/Scripts/python.exe -m app.cli.concierge pack --user priya job1.txt job2.txt [--mode quick] [--template modern]
      -> concierge/priya/<job>/ resume.pdf, ats.txt, review.md, cover_letter.md, outreach.md, pack.json

Job files are plain text copied from the posting (paste it yourself; never scrape LinkedIn/Indeed/Naukri).
Needs GROQ_API_KEY. Contact details are removed before anything is sent to Groq.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path

from app.core.env import load_dotenv
from app.features.generation.pipeline import PackResult, generate_pack
from app.features.profiles.parse import parse_resume
from app.llm.client import GroqLLM
from app.llm.pii import restore_placeholders
from app.llm.schemas import CareerProfile, ContactDetails

ROOT = Path.cwd() / "concierge"


def _user_dir(user: str) -> Path:
    if not re.fullmatch(r"[a-z0-9-]{2,40}", user):
        raise SystemExit("--user must be a short slug like 'priya' or 'jordan-k'")
    return ROOT / user


async def cmd_parse(args: argparse.Namespace) -> None:
    out = _user_dir(args.user)
    out.mkdir(parents=True, exist_ok=True)
    llm = GroqLLM(budget_usd=0.25)
    profile, contact = await parse_resume(llm, Path(args.resume), mode=args.mode)
    (out / "profile.json").write_text(profile.model_dump_json(indent=2), encoding="utf-8")
    (out / "contact.json").write_text(contact.model_dump_json(indent=2), encoding="utf-8")
    facts = profile.all_facts()
    print(f"Parsed {len(profile.experience)} roles, {len(profile.projects)} projects, {len(facts)} facts, "
          f"{len(profile.skills)} skills  (${llm.spent_usd:.4f})")
    print(f"Contact found locally (never sent to Groq): name={contact.full_name!r} email={contact.email!r} phone={contact.phone!r}")
    no_metrics = [f.id for f in facts.values() if not f.metrics]
    print(f"\nNext: review {out / 'profile.json'} and {out / 'contact.json'} WITH THE USER.")
    print(f"  {len(no_metrics)} facts have no numbers. Ask the user for metrics on the important ones.")
    if not contact.full_name:
        print("  The name wasn't detected; fill it in contact.json.")


def _bullets_md(pack: PackResult, profile: CareerProfile) -> str:
    exp = {e.id: e for e in profile.experience}
    lines = [f"**Summary:** {pack.resume.summary}", ""]
    for role in pack.resume.experience:
        e = exp.get(role.experience_id)
        lines.append(f"**{e.title}, {e.company}**" if e else f"**{role.experience_id}**")
        lines += [f"- {b.text}  _(facts: {', '.join(b.source_fact_ids)})_" for b in role.bullets]
    return "\n".join(lines)


def _review_md(pack: PackResult, profile: CareerProfile, ats: dict | None) -> str:
    gaps = [m for m in pack.match.requirement_matches if m.status != "evidenced"]
    req = {r.id: r for r in pack.job.requirements}
    out = [
        f"# Review: {pack.job.title} @ {pack.job.company or 'unknown company'}",
        "",
        "## Checklist before sending (concierge-playbook §3)",
        "- [ ] Every bullet is true to the profile (check the cited facts below)",
        "- [ ] No gap below was claimed anywhere",
        "- [ ] ATS check passed (see ats.txt)",
        "- [ ] Cover letter has a specific hook; outreach within limits",
        "- [ ] Logged every fix I made (each one becomes an eval case)",
        "",
        f"## Angle\n{pack.match.angle}",
        "",
        "## Gaps and partial matches (must NOT appear as claims)",
        *[f"- **{m.status}**: {req[m.requirement_id].text if m.requirement_id in req else m.requirement_id} ({m.note})" for m in gaps],
        "",
        "## Questions to ask the user",
        *[f"- {q.question}" for q in pack.match.gap_questions],
        "",
        "## Resume bullets with their sources",
        _bullets_md(pack, profile),
        "",
        "## Automated findings",
        f"- Revised by the pipeline: {pack.revised}",
        *[f"- verify ({v.severity}) {v.kind} @ {v.location}: {v.explanation}" for v in pack.verify.violations],
        *[f"- lint ({f['severity']}) {f['check']} @ {f['location']}: {f['message']}" for f in pack.lint_final],
        *[f"- letter lint: {f['message']}" for f in pack.cover_letter_lint],
        *[f"- outreach lint: {f['location']}: {f['message']}" for f in pack.outreach_lint],
        "",
        f"ATS: {'PASS' if ats and ats.get('parse_ok') else 'CHECK ats.txt'} · cost ${sum(c.cost_usd for c in pack.calls):.4f} · {pack.wall_ms / 1000:.1f}s",
    ]
    return "\n".join(out) + "\n"


async def cmd_pack(args: argparse.Namespace) -> None:
    from app.features.rendering.ats_roundtrip import extract
    from evals.graders.ats import render_and_check

    out = _user_dir(args.user)
    profile = CareerProfile.model_validate_json((out / "profile.json").read_text(encoding="utf-8"))
    contact = ContactDetails.model_validate_json((out / "contact.json").read_text(encoding="utf-8"))
    if not contact.full_name or not contact.email:
        raise SystemExit(f"Fill in full_name and email in {out / 'contact.json'} first.")

    async def one(job_file: str) -> None:
        jd_text = Path(job_file).read_text(encoding="utf-8")
        llm = GroqLLM(budget_usd=0.5)
        pack = await generate_pack(llm, profile, contact, jd_text, mode=args.mode)
        slug = re.sub(r"[^a-z0-9]+", "-", f"{pack.job.company or 'job'}-{pack.job.title}".lower()).strip("-")[:60]
        job_dir = out / slug
        job_dir.mkdir(parents=True, exist_ok=True)
        ats, pdf = render_and_check(pack.resume, profile, contact, pack, template=args.template)
        if pdf:
            name = re.sub(r"[^A-Za-z]+", "-", contact.full_name).strip("-")
            company = re.sub(r"[^A-Za-z0-9]+", "-", pack.job.company or "Company").strip("-")
            (job_dir / f"{name}-Resume-{company}.pdf").write_bytes(pdf)
            seen = extract(pdf).primary
            (job_dir / "ats.txt").write_text(json.dumps(ats, indent=2) + "\n\n--- WHAT THE ATS SEES ---\n\n" + seen, encoding="utf-8")
        letter = "\n\n".join([pack.cover_letter.salutation, *pack.cover_letter.paragraphs, pack.cover_letter.closing, "{{FULL_NAME}}"])
        (job_dir / "cover_letter.md").write_text(restore_placeholders(letter, contact) + "\n", encoding="utf-8")
        o = pack.outreach
        outreach = (f"## Recruiter email\n**Subject:** {o.recruiter_email_subject}\n\n{o.recruiter_email_body}\n\n"
                    f"## LinkedIn note ({len(o.linkedin_note)} chars)\n{o.linkedin_note}\n\n"
                    f"## Referral ask\n{o.referral_ask}\n\n## Follow-up (7-10 days after applying)\n{o.follow_up}\n")
        (job_dir / "outreach.md").write_text(restore_placeholders(outreach, contact), encoding="utf-8")
        (job_dir / "review.md").write_text(_review_md(pack, profile, ats), encoding="utf-8")
        (job_dir / "pack.json").write_text(pack.model_dump_json(indent=2), encoding="utf-8")
        status = "ATS PASS" if ats.get("parse_ok") else "ATS CHECK"
        print(f"  {slug}: {status} · revised={pack.revised} · ${llm.spent_usd:.4f} · {pack.wall_ms / 1000:.1f}s -> {job_dir}")

    await asyncio.gather(*(one(f) for f in args.jobs))
    print("\nOpen each review.md and work through the checklist before sending anything to the user.")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    load_dotenv()  # GROQ_API_KEY from a gitignored .env, if present
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    pp = sub.add_parser("parse", help="resume file -> profile.json + contact.json")
    pp.add_argument("--user", required=True)
    pp.add_argument("--mode", default="deep", choices=["deep", "quick"])
    pp.add_argument("resume")
    pk = sub.add_parser("pack", help="generate packs for job description text files")
    pk.add_argument("--user", required=True)
    pk.add_argument("--mode", default="deep", choices=["deep", "quick"])
    pk.add_argument("--template", default="classic", choices=["classic", "modern"])
    pk.add_argument("jobs", nargs="+")
    args = p.parse_args()
    if not os.environ.get("GROQ_API_KEY"):
        print("GROQ_API_KEY is not set (Developer-tier key from console.groq.com).", file=sys.stderr)
        return 2
    asyncio.run(cmd_parse(args) if args.cmd == "parse" else cmd_pack(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
