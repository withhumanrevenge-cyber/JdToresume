"""Eval runner and model bake-off (ROADMAP Phase 0).

Windows, from the repo root (never `uv run`: Application Control blocks its launcher):
  .venv/Scripts/python.exe -m evals.run_eval --estimate          # no API calls: cost + rate-limit estimate
  .venv/Scripts/python.exe -m evals.run_eval --smoke             # first 3 cases x default models, with judge
  .venv/Scripts/python.exe -m evals.run_eval --models openai/gpt-oss-120b qwen/qwen3.8-27b --cases us-backend-mid

Needs GROQ_API_KEY in the environment (except --estimate). Reports go to evals/reports/<timestamp>/.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from itertools import combinations
from pathlib import Path
from typing import Any

from groq import AsyncGroq

from app.core.env import load_dotenv

from app.features.generation.pipeline import PackResult, generate_pack
from app.llm.client import GroqLLM, to_data
from app.llm.prompts import global_policy, prompt_version, step_prompt
from app.llm.router import GPT_OSS_20B, GPT_OSS_120B, PRICES, ROUTES
from evals.case import EvalCase, load_cases
from evals.graders.ats import render_and_check
from evals.graders.deterministic import PackGrade, grade_pack, summarize
from evals.graders.judge import JUDGE_PROMPT, judge_pair

DEFAULT_MODELS = [GPT_OSS_120B, GPT_OSS_20B]
REPORTS = Path(__file__).parent / "reports"
STEPS = ["jd_extract", "match_plan", "resume_tailor", "cover_letter", "outreach", "verify", "revise"]
FREE_TIER_TPM = 8_000  # Groq base limits for gpt-oss models (Oct 2026); Developer tier is far higher


# --------------------------------------------------------------------------- estimate (no API calls)

def _tok(text: str) -> int:
    return max(1, len(text) // 4)


def estimate(cases: list[EvalCase], models: list[str], judge_model: str, with_judge: bool) -> None:
    """Rough token/cost model: chars/4 for inputs, typical output sizes incl. reasoning tokens."""
    out_tokens = {"jd_extract": 2000, "match_plan": 3500, "resume_tailor": 5000, "cover_letter": 2000,
                  "outreach": 1200, "verify": 1500, "revise": 5000}
    sizes = {"job_spec": 1500, "match_report": 2000, "tailored_resume": 2200, "violations": 600}
    system = _tok(global_policy())
    print(f"{'model':24s} {'case':28s} {'in tok':>8s} {'out tok':>8s} {'$/pack':>8s} {'peak req tok':>12s}")
    grand = 0.0
    worst_peak = 0
    for model in models:
        price = PRICES[model]
        model_total = 0.0
        for case in cases:
            prof, jd = _tok(to_data(case.profile)), _tok(case.jd_text)
            tin = tout = 0
            cost = 0.0
            peak = 0
            for step in STEPS:
                runs = 0.5 if step == "revise" else 1.0
                body = _tok(step_prompt(step))
                if step == "jd_extract":
                    inp, cached = system + body + jd, 0
                else:
                    extra = sizes["job_spec"]
                    if step in ("resume_tailor", "cover_letter", "outreach", "revise"):
                        extra += sizes["match_report"]
                    if step in ("verify", "revise"):
                        extra += sizes["tailored_resume"]
                    if step == "revise":
                        extra += sizes["violations"]
                    inp = system + prof + body + extra
                    cached = system + prof  # automatic prefix cache (gpt-oss) after match_plan warms it
                out = out_tokens[step]
                cfg = ROUTES["deep"][step]
                peak = max(peak, inp + cfg.max_completion_tokens)
                tin += int(inp * runs)
                tout += int(out * runs)
                cost += runs * price.cost(inp, cached if step != "match_plan" else 0, out)
            model_total += cost
            worst_peak = max(worst_peak, peak)
            print(f"{model:24s} {case.id:28s} {tin:8d} {tout:8d} {cost:8.4f} {peak:12d}")
        print(f"{model:24s} {'TOTAL (' + str(len(cases)) + ' cases)':28s} {'':8s} {'':8s} {model_total:8.4f}")
        grand += model_total
    if with_judge and len(models) >= 2:
        jp = PRICES[judge_model]
        per_call_in = _tok(JUDGE_PROMPT) + 2 * sizes["tailored_resume"] + max(
            _tok(to_data(c.profile)) + _tok(c.jd_text) for c in cases)
        pairs = len(list(combinations(models, 2)))
        judge_cost = len(cases) * pairs * 2 * jp.cost(per_call_in, 0, 4000)
        print(f"judge ({judge_model}): {len(cases)} cases x {pairs} pairs x 2 orders = ${judge_cost:.4f}")
        grand += judge_cost
    print(f"\nESTIMATED TOTAL: ${grand:.4f} (list prices; reasoning length varies, so allow up to 2x)")
    print(f"Rate limits: a single request can need ~{worst_peak:,} tokens (input + max_completion_tokens). "
          f"Groq's base/free limit for gpt-oss is {FREE_TIER_TPM:,} tokens/min and 200K/day, which cannot run this "
          f"pipeline. Use a Developer-tier key (pay as you go) for evals.")


# --------------------------------------------------------------------------- ATS hook

def ats_check(case: EvalCase, pack: PackResult) -> tuple[dict[str, Any] | None, bytes | None]:
    """Render the final resume (fit-to-page) and run the ATS round-trip. A render crash is a failed check, not a skip."""
    try:
        return render_and_check(pack.resume, case.profile, case.contact, pack)
    except Exception as exc:
        return {"parse_ok": False, "issues": [f"render crashed: {type(exc).__name__}: {exc}"[:300]]}, None


# --------------------------------------------------------------------------- run

async def run(args: argparse.Namespace, cases: list[EvalCase]) -> Path:
    out_dir = REPORTS / datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    client = AsyncGroq(max_retries=5, timeout=180)
    sem = asyncio.Semaphore(args.concurrency)
    spent = {"usd": 0.0}
    packs: dict[str, dict[str, PackResult]] = {m: {} for m in args.models}
    grades: dict[str, list[PackGrade]] = {m: [] for m in args.models}
    failures: list[dict[str, str]] = []

    async def run_one(model: str, case: EvalCase) -> None:
        if spent["usd"] >= args.budget:
            failures.append({"model": model, "case": case.id, "error": "skipped: run budget exhausted"})
            return
        llm = GroqLLM(budget_usd=args.per_pack_budget, client=client, semaphore=sem)
        try:
            pack = await generate_pack(llm, case.profile, case.contact, case.jd_text, mode=args.mode, model_override=model)
        except Exception as exc:  # recorded, never hidden: a failed pack is a result too
            failures.append({"model": model, "case": case.id, "error": f"{type(exc).__name__}: {exc}"[:600]})
            return
        finally:
            spent["usd"] += llm.spent_usd
        packs[model][case.id] = pack
        ats, pdf = ats_check(case, pack)
        grades[model].append(grade_pack(case, model, pack, ats))
        pack_dir = out_dir / "packs" / model.replace("/", "__")
        pack_dir.mkdir(parents=True, exist_ok=True)
        (pack_dir / f"{case.id}.json").write_text(pack.model_dump_json(indent=2), encoding="utf-8")
        if pdf:
            (pack_dir / f"{case.id}.pdf").write_bytes(pdf)  # synthetic data only, for human review
        print(f"  done {model} / {case.id}  ${sum(c.cost_usd for c in pack.calls):.4f}  {pack.wall_ms / 1000:.1f}s", flush=True)

    print(f"Running {len(cases)} cases x {len(args.models)} models (mode={args.mode}) -> {out_dir}")
    await asyncio.gather(*(run_one(m, c) for m in args.models for c in cases))

    judgements: list[dict[str, Any]] = []
    if args.judge and len(args.models) >= 2:
        print(f"Judging with {args.judge_model} ...")
        jobs = []
        for case in cases:
            for a, b in combinations(args.models, 2):
                if case.id in packs[a] and case.id in packs[b]:
                    jobs.append((case, a, b))

        async def judge_one(case: EvalCase, a: str, b: str) -> None:
            if spent["usd"] >= args.budget:
                return
            try:
                async with sem:
                    result = await judge_pair(client, args.judge_model, case.profile, case.jd_text,
                                              a, packs[a][case.id].resume, b, packs[b][case.id].resume)
            except Exception as exc:
                failures.append({"model": f"judge {a} vs {b}", "case": case.id, "error": f"{type(exc).__name__}: {exc}"[:600]})
                return
            spent["usd"] += result["cost_usd"]
            judgements.append({"case": case.id, **result})

        await asyncio.gather(*(judge_one(*job) for job in jobs))

    results = {
        "started": out_dir.name, "dataset": args.dataset, "mode": args.mode, "models": args.models,
        "judge_model": args.judge_model if args.judge else None,
        "prompt_versions": {s: prompt_version(s) for s in STEPS},
        "spent_usd": round(spent["usd"], 5),
        "summary": {m: summarize(grades[m]) for m in args.models},
        "win_rates": win_rates(args.models, judgements),
        "grades": {m: [g.model_dump() for g in grades[m]] for m in args.models},
        "judgements": judgements, "failures": failures,
    }
    (out_dir / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    (out_dir / "report.md").write_text(render_report(results), encoding="utf-8")
    return out_dir


def win_rates(models: list[str], judgements: list[dict[str, Any]]) -> dict[str, float | None]:
    rates: dict[str, float | None] = {}
    for m in models:
        games = [j for j in judgements if m in (j["a"], j["b"])]
        if not games:
            rates[m] = None
            continue
        points = sum(1.0 if j["winner"] == m else 0.5 if j["winner"] == "tie" else 0.0 for j in games)
        rates[m] = round(points / len(games), 3)
    return rates


def render_report(r: dict[str, Any]) -> str:
    models = r["models"]
    lines = [
        f"# Eval report {r['started']}",
        "",
        f"Dataset `{r['dataset']}` · mode `{r['mode']}` · judge `{r['judge_model']}` · spent **${r['spent_usd']:.4f}**",
        "",
        "Prompt versions: " + ", ".join(f"`{v}`" for v in r["prompt_versions"].values()),
        "",
        "## Summary",
        "",
        "| Metric | " + " | ".join(models) + " |",
        "|---|" + "---|" * len(models),
    ]
    metrics = sorted({k for s in r["summary"].values() for k in s})
    for key in metrics:
        lines.append(f"| {key} | " + " | ".join(str(r["summary"][m].get(key, "")) for m in models) + " |")
    lines.append("| pairwise win rate | " + " | ".join(str(r["win_rates"].get(m)) for m in models) + " |")
    lines += ["", "## Hard gates", ""]
    for m in models:
        s = r["summary"][m]
        if not s:
            lines.append(f"- `{m}`: no successful packs")
            continue
        fab = "PASS" if s["fabrication_rate"] == 0 else f"FAIL ({s['fabrication_rate']:.0%})"
        ats = "n/a (renderer not wired)" if s["ats_parse_pass"] is None else ("PASS" if s["ats_parse_pass"] == 1 else f"FAIL ({s['ats_parse_pass']:.0%})")
        lines.append(f"- `{m}`: fabrication {fab} · ATS parse {ats}")
    lines += ["", "## Per case", "", "| case | model | fabrication | traps in resume | evidenced coverage | verify high | revised | $ | s |",
              "|---|---|---|---|---|---|---|---|---|"]
    for m in models:
        for g in r["grades"][m]:
            lines.append(f"| {g['case_id']} | {m} | {'YES' if g['fabrication'] else 'no'} | {', '.join(g['trap_hits_resume']) or '-'} | "
                         f"{g['evidenced_coverage']:.0%} | {g['verify_high_initial']} | {'yes' if g['revised'] else 'no'} | "
                         f"{g['cost_usd']:.4f} | {g['wall_ms'] / 1000:.1f} |")
    fab_details = [(m, g) for m in models for g in r["grades"][m] if g["fabrication"]]
    if fab_details:
        lines += ["", "## Fabrication details", ""]
        for m, g in fab_details:
            lines.append(f"- **{g['case_id']} / {m}**: " + "; ".join(g["fabrication_reasons"]))
    if r["judgements"]:
        lines += ["", "## Pairwise judgements", "", "| case | A | B | winner | rationale (order 1) |", "|---|---|---|---|---|"]
        for j in r["judgements"]:
            lines.append(f"| {j['case']} | {j['a']} | {j['b']} | {j['winner']} | {j['orders'][0]['rationale'][:200]} |")
    if r["failures"]:
        lines += ["", "## Failures", ""]
        lines += [f"- {f['case']} / {f['model']}: `{f['error']}`" for f in r["failures"]]
    return "\n".join(lines) + "\n"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    load_dotenv()  # GROQ_API_KEY from a gitignored .env, if present
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dataset", default="v0")
    p.add_argument("--cases", nargs="*", help="case ids (default: all)")
    p.add_argument("--smoke", action="store_true", help="first 3 cases only")
    p.add_argument("--models", nargs="*", default=DEFAULT_MODELS, choices=sorted(PRICES))
    p.add_argument("--mode", default="deep", choices=["deep", "quick"])
    p.add_argument("--no-judge", dest="judge", action="store_false")
    p.add_argument("--judge-model", default=GPT_OSS_120B, choices=sorted(PRICES))
    p.add_argument("--concurrency", type=int, default=3, help="max concurrent API requests")
    p.add_argument("--budget", type=float, default=2.0, help="stop starting new work after this many USD")
    p.add_argument("--per-pack-budget", type=float, default=0.5)
    p.add_argument("--estimate", action="store_true", help="print the cost estimate and exit (no API calls)")
    p.add_argument("--fail-on-gates", action="store_true",
                   help="exit 1 if a hard gate fails or a model produced no packs (for CI)")
    args = p.parse_args()

    cases = load_cases(args.dataset, args.cases)
    if args.smoke:
        cases = cases[:3]
    if not cases:
        print(f"No cases found in evals/datasets/{args.dataset}/cases", file=sys.stderr)
        return 2
    if args.estimate:
        estimate(cases, args.models, args.judge_model, args.judge)
        return 0
    if not os.environ.get("GROQ_API_KEY"):
        print("GROQ_API_KEY is not set. Create a key at console.groq.com (Developer tier recommended) and put GROQ_API_KEY=... in a .env file at the repo root (gitignored) or in "
              "your environment, then re-run. Use --estimate to see the cost first.", file=sys.stderr)
        return 2
    out_dir = asyncio.run(run(args, cases))
    print((out_dir / "report.md").read_text(encoding="utf-8"))
    if args.fail_on_gates:
        failed = failed_gates(json.loads((out_dir / "results.json").read_text(encoding="utf-8")))
        for problem in failed:
            print(f"HARD GATE FAILED: {problem}", file=sys.stderr)
        return 1 if failed else 0
    return 0


def failed_gates(results: dict[str, Any]) -> list[str]:
    """CLAUDE.md non-negotiable #5: fabrication = 0 and ATS parse = 100%. A model with no packs fails too."""
    problems = []
    for model in results["models"]:
        summary = results["summary"].get(model) or {}
        if not summary:
            problems.append(f"{model}: no successful packs")
            continue
        if summary["fabrication_rate"] != 0:
            problems.append(f"{model}: fabrication rate {summary['fabrication_rate']:.0%}")
        if summary["ats_parse_pass"] is not None and summary["ats_parse_pass"] != 1:
            problems.append(f"{model}: ATS parse pass {summary['ats_parse_pass']:.0%}")
    return problems


if __name__ == "__main__":
    raise SystemExit(main())
