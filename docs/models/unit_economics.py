"""Reproduces the numbers in docs/COSTS.md (sec. 1 cost per pack, sec. 2 plan comparison, sec. 5 scenarios).

Run (Windows): .venv/Scripts/python.exe docs/models/unit_economics.py

Provider: Groq (ADR-0001). The Claude Opus 5.5 row is kept only as a reference for the decision.
Update PRICES when list prices change, and STEPS with real `llm_calls` ledger medians once beta traffic exists.
"""

# $ per 1M tokens. Groq: automatic prefix caching on gpt-oss at 50% off, no cache-write premium.
PRICES = {
    "gpt-oss-120b": dict(inp=0.15, out=0.60, cache_read=0.075, cache_write=0.15),
    "gpt-oss-20b":  dict(inp=0.075, out=0.30, cache_read=0.0375, cache_write=0.075),
    "qwen3.8-27b":  dict(inp=0.80, out=4.00, cache_read=0.80, cache_write=0.80),   # preview; no caching
    "claude-opus-5-5 (reference)": dict(inp=4.00, out=20.0, cache_read=0.20, cache_write=5.00),
}

# step: (uncached input, cache-read input, cache-write input, output incl. reasoning tokens, runs per pack)
STEPS = {
    "jd_extract":    (2000, 1500,    0, 2000, 1.0),
    "match_plan":    (1200,  500, 6500, 3500, 1.0),   # warms the shared system+profile prefix
    "resume_tailor": (3200, 7000,    0, 5000, 1.0),
    "verify":        (3700, 6000,    0, 1500, 1.0),
    "revise":        (4500, 7000,    0, 5000, 0.5),   # gpt-oss revises more often than assumed for Claude
    "cover_letter":  (3200, 7000,    0, 2000, 1.0),
    "outreach":      (3200, 7000,    0, 1200, 1.0),
}
RESUME_STEPS = ("jd_extract", "match_plan", "resume_tailor", "verify", "revise")
_writing = ("match_plan", "resume_tailor", "revise", "cover_letter")

MIXES = {  # which model runs each step
    "Deep: gpt-oss-120b everywhere": {s: "gpt-oss-120b" for s in STEPS},
    "Quick: gpt-oss-20b everywhere": {s: "gpt-oss-20b" for s in STEPS},
    "Qwen 3.8 writing + 20b rest": {s: ("qwen3.8-27b" if s in _writing else "gpt-oss-20b") for s in STEPS},
    "Reference: Claude Opus 5.5 everywhere": {s: "claude-opus-5-5 (reference)" for s in STEPS},
}


def step_cost(step: str, model: str) -> float:
    unc, cr, cw, out, runs = STEPS[step]
    p = PRICES[model]
    return runs * (unc * p["inp"] + cr * p["cache_read"] + cw * p["cache_write"] + out * p["out"]) / 1e6


def pack_cost(mix: str, steps=tuple(STEPS)) -> float:
    return sum(step_cost(s, MIXES[mix][s]) for s in steps)


def one_off(model: str, inp: int, out: int, cache_read: int = 0) -> float:
    p = PRICES[model]
    return (inp * p["inp"] + out * p["out"] + cache_read * p["cache_read"]) / 1e6


SCAN = {m: one_off(m, 6500, 1500, cache_read=1500) for m in PRICES}       # free match scan
ONBOARD = {m: one_off(m, 7000, 4500) for m in PRICES}                     # one-time resume parse (text in)
SCREENSHOT_QWEN = 3 * 2048 * PRICES["qwen3.8-27b"]["inp"] / 1e6           # 3 images x 2,048 tokens each

# ---- market & scenario assumptions (COSTS.md sec. 2, 5) ----
MARKETS = {  # ARPPU $/mo net, payment fee %, fixed fee, packs per paid user/mo, scans per free MAU/mo
    "IN": dict(arppu=3.40, fee_pct=0.025, fee_fixed=0.00, packs=15, scans=5),
    "US": dict(arppu=20.0, fee_pct=0.05, fee_fixed=0.30, packs=12, scans=4),
}
NEW_SHARE = 0.35  # share of MAU that signed up this month
SCENARIOS = {  # market: (MAU, paid conversion)
    "Conservative": {"IN": (8_000, 0.015), "US": (3_000, 0.04)},
    "Base":         {"IN": (50_000, 0.02), "US": (15_000, 0.05)},
    "Viral":        {"IN": (300_000, 0.02), "US": (80_000, 0.05)},
}
INFRA = {"Conservative": 300, "Base": 1200, "Viral": 6000}

DEEP, QUICK, OPUS = "Deep: gpt-oss-120b everywhere", "Quick: gpt-oss-20b everywhere", "Reference: Claude Opus 5.5 everywhere"
PLANS = {  # paid mix, free mix, free packs used per free MAU per month, scan + onboarding model
    "G1 Groq Deep for everyone, 3 free packs/mo (2 used)": dict(paid=DEEP, free=DEEP, free_packs=2.0, cheap="gpt-oss-120b"),
    "G2 Groq: Quick for free tier, Deep for paid (recommended)": dict(paid=DEEP, free=QUICK, free_packs=2.0, cheap="gpt-oss-20b"),
    "G3 Groq: Qwen 3.8 writing for paid, Quick free": dict(paid="Qwen 3.8 writing + 20b rest", free=QUICK, free_packs=2.0, cheap="gpt-oss-20b"),
    "Reference: Claude Opus everywhere, 3 free packs/mo": dict(paid=OPUS, free=OPUS, free_packs=2.0, cheap="claude-opus-5-5 (reference)"),
}


def month(plan: dict, scenario: dict, infra: float) -> dict:
    rev = fees = llm = paid_total = mau_total = 0.0
    for mkt, (mau, conv) in scenario.items():
        m = MARKETS[mkt]
        paid, new = mau * conv, mau * NEW_SHARE
        free = mau - paid
        r = paid * m["arppu"]
        rev += r
        fees += r * m["fee_pct"] + paid * m["fee_fixed"]
        llm += paid * m["packs"] * pack_cost(plan["paid"])
        llm += free * (plan["free_packs"] * pack_cost(plan["free"]) + m["scans"] * SCAN[plan["cheap"]])
        llm += new * ONBOARD[plan["cheap"]]
        paid_total += paid
        mau_total += mau
    gross = rev - fees - llm - infra
    return dict(mau=mau_total, paid=paid_total, mrr=rev, fees=fees, llm=llm, infra=infra, gross=gross, gm=gross / rev)


if __name__ == "__main__":
    print("== Cost per pack (COSTS sec. 1)")
    for k in MIXES:
        print(f"  {k:42s} full ${pack_cost(k):.4f}   resume-only ${pack_cost(k, RESUME_STEPS):.4f}")
    print("  free scan:   " + "  ".join(f"{m} ${v:.4f}" for m, v in SCAN.items()))
    print("  onboarding:  " + "  ".join(f"{m} ${v:.4f}" for m, v in ONBOARD.items()))
    print(f"  screenshot JD via qwen3.8-27b vision (3 images): ${SCREENSHOT_QWEN:.4f}")

    print("\n== Gross margin by plan and scenario (COSTS sec. 2)")
    for name, plan in PLANS.items():
        cells = [f"{s}: {month(plan, sc, INFRA[s])['gm']:>6.0%}" for s, sc in SCENARIOS.items()]
        print(f"  {name:58s} " + "   ".join(cells))

    print("\n== Month-12 scenarios, G2 (COSTS sec. 5)")
    plan = PLANS["G2 Groq: Quick for free tier, Deep for paid (recommended)"]
    for s, sc in SCENARIOS.items():
        r = month(plan, sc, INFRA[s])
        print(f"  {s:12s} MAU {r['mau']:>8,.0f}  paid {r['paid']:>6,.0f}  MRR ${r['mrr']:>8,.0f}  fees ${r['fees']:>6,.0f}  "
              f"LLM ${r['llm']:>7,.0f}  infra ${r['infra']:>5,.0f}  gross ${r['gross']:>8,.0f}  GM {r['gm']:.0%}")
