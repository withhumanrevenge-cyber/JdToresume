# Costs, Pricing & Unit Economics

All prices are USD, current as of October 2026. LLM prices are GroqCloud list prices (see [ADR-0001](adr/ADR-0001-llm-provider-groq.md)). AWS and SaaS prices are public list prices (approximate, from memory; verify before budgeting). INR at ~₹88/$. Every number in §1, §2 and §5 is reproduced by [`docs/models/unit_economics.py`](models/unit_economics.py).

---

## 1. LLM cost per application pack

### 1.1 Groq prices used ($ per 1M tokens)

| Model | Input | Cached input | Output | Notes |
|-------|-------|--------------|--------|-------|
| `openai/gpt-oss-120b` (Deep) | 0.15 | 0.075 | 0.60 | Production model; automatic prefix caching (50% off, no write fee) |
| `openai/gpt-oss-20b` (Quick) | 0.075 | 0.0375 | 0.30 | Production model; about 2× faster |
| `qwen/qwen3.8-27b` (vision, bake-off candidate) | 0.80 | – | 4.00 | **Preview**; 2,048 tokens per image, at most 3 images |
| *Reference: Claude Opus 5.5* | *4.00* | *0.20* | *20.00* | *The previous plan, kept for comparison* |

The Batch API is 50% cheaper and doesn't count against rate limits. It's used for evals and offline jobs, never for interactive generation, and it isn't available with Zero Data Retention on.

### 1.2 Token budget per step (one "pack" = resume + cover letter + outreach)

| Step | Uncached in | Cached in | Prefix-warming in | Output (incl. reasoning) | Runs |
|------|-------------|-----------|-------------------|--------------------------|------|
| JD extract | 2,000 | 1,500 | – | 2,000 | 1 |
| Match & plan | 1,200 | 500 | 6,500 (warms the shared prefix) | 3,500 | 1 |
| Resume tailor | 3,200 | 7,000 | – | 5,000 | 1 |
| Verify | 3,700 | 6,000 | – | 1,500 | 1 |
| Revise | 4,500 | 7,000 | – | 5,000 | 0.5 (assumed 50% of runs) |
| Cover letter | 3,200 | 7,000 | – | 2,000 | 1 |
| Outreach pack | 3,200 | 7,000 | – | 1,200 | 1 |

Reasoning tokens are billed as output, so per-step `reasoning_effort` is the main cost lever. **Replace these budgets with real ledger medians after the first bake-off run.**

### 1.3 Cost per pack by model mix

| Mix | Full pack | Resume only |
|-----|-----------|-------------|
| **Deep**: gpt-oss-120b everywhere | **$0.017** | $0.013 |
| **Quick**: gpt-oss-20b everywhere | **$0.008** | $0.007 |
| Qwen 3.8 for writing + gpt-oss-20b for the rest | $0.082 | $0.065 |
| *Reference: Claude Opus 5.5 everywhere* | *$0.468* | *$0.376* |

Extras:
- Free match scan: **$0.001** on 20b, $0.002 on 120b.
- One-time resume onboarding parse: $0.002–0.004.
- Screenshot JD via Qwen vision (3 images): ~$0.005.

> The final mix is decided by the **Phase 0 bake-off** (`evals/run_eval.py`). Quality gates (fabrication = 0, ATS parse = 100%, pairwise preference) decide whether 20b is good enough for Quick, and whether Qwen's writing is worth ~5× the cost.

---

## 2. What Groq changes: LLM cost stops being the constraint

The model is month 12 (scenarios in §5):
- Free MAU use 2 of their **3 monthly** free packs, plus scans.
- New signups are 35% of MAU, and each gets the onboarding parse.
- Paid users make 12 (US) or 15 (India) packs a month.

| Plan | Conservative (11k MAU) | Base (65k MAU) | Viral (380k MAU) |
|------|------------------------|----------------|------------------|
| G1: Groq Deep for everyone | 64% | 70% | 70% |
| **G2: Quick (20b) for the free tier, Deep (120b) for paid (recommended)** | **73%** | **78%** | **78%** |
| G3: Qwen 3.8 writing for paid, Quick free | 65% | 69% | 69% |
| *Reference: Claude Opus everywhere, same free tier* | *−448%* | *−402%* | *−436%* |

*(GM = MRR minus payment fees, LLM and infra.)*

**What it means:**
1. **The free tier can be generous and monthly.** On Claude, the free tier was the cost center and forced lifetime-only free packs plus a Haiku-only Quick mode. On Groq, 3 free packs a month plus unlimited scans costs pennies per user.
2. **Quick vs. Deep is now about speed and quality, not survival.** Quick (20b) is the free tier and the instant scan; Deep (120b) is the paid default. If the bake-off shows 20b is as good, the split collapses into one mode.
3. **The constraints move elsewhere:**
   - **Quality:** can open models match frontier writing and stay truthful? The eval gates measure this.
   - **Rate limits and capacity** (ARCHITECTURE §15).
   - **Model churn** on Groq's catalog.
4. **The paid tiers stay far above water in both markets:**

| Market | ARPPU | LLM / paid user / month (Deep) | Contribution after LLM + payment fees |
|--------|-------|--------------------------------|----------------------------------------|
| India (₹299 avg) | $3.40 | $0.25 | **$3.07 (90%)** |
| US/global ($20 avg) | $20.00 | $0.20 | **$18.50 (92%)** |

---

## 3. Pricing

**Principles** (backed by the benchmarks in [MARKET.md](MARKET.md#pricing-benchmarks)):
- **Job seekers buy in bursts and leave once hired.** A search lasts ~3–4 months, so the **quarterly plan is the anchor**. Weekly subscriptions keep only 3.4% of users through year one and anger them, so **the weekly option is a one-time pass, not a subscription.**
- **Trust is the wedge.** The category is known for $1.95 trials that roll into charges every 4 weeks, and for 2.0–2.9 Trustpilot scores. We use no card-up-front trials, one-click cancel, renewal reminders and plain-language prices.
- **Purchasing-power pricing.** India gets its own prices, with **one-time UPI passes** (Indian buyers prefer them to auto-debit).
- **Free value is the diagnosis plus a real taste** (the scan plus a few packs). **Paid value is volume and depth:** unlimited Deep packs, cover letters, outreach, the tracker. Never watermark a resume: it hurts parsing and trust.

| Plan | US / global | India | Billing | Mode | Includes |
|------|-------------|-------|---------|------|----------|
| Free | $0 | ₹0 | – | Quick | Unlimited match scans (fair use 20/day), **3 Quick packs per month**, +3 per successful referral, 1 Deep pack at signup |
| Sprint pass (7 days) | **$12** | **₹149** | **One-time, no renewal** | Quick + Deep | Unlimited packs (fair use 100/week), all templates, cover letters, outreach |
| Pro monthly | **$24/mo** | **₹399 / 30 days** (one-time UPI, or UPI Autopay if the user opts in) | Monthly, one-click cancel | Quick + Deep | Sprint + tracker + interview prep (Phase 3) + priority queue |
| **Pro quarter** (the anchor) | **$59 / 90 days** | **₹999 / 90 days** | Quarterly, one-click cancel | same | same; "most job searches take 3–4 months" |
| Credit pack | – | **₹99 for 10 Deep packs** | One-time | Deep | UPI one-tap |

Where this sits: below Teal, Enhancv and Rezi ($29/mo), Simplify ($39.99/mo) and Jobscan ($49.95/mo). The Sprint pass is in line with weekly passes in the category ($9–20). India sits well below Naukri Pro (₹999/mo) and LinkedIn Premium (₹999–1,899), next to the ₹99–₹699 one-time passes Indian users already buy. We also sit above "free ChatGPT", and justify the price with a PDF that parses, the truthfulness guarantee, outreach and speed.

**Payments:**
- An India entity selling in India: **Razorpay** (UPI, cards, ~2% fee). International cards through Razorpay, or a Merchant of Record (Paddle, or the India-founded Dodo Payments), which also handles global VAT and sales tax for a ~5% + $0.50 fee.
- A US entity: **Stripe** (2.9% + 30¢; +1.5% for international cards) + Stripe Tax, plus Razorpay through an Indian subsidiary later.

---

## 4. Infrastructure cost by stage (monthly, approximate)

| Item | MVP / beta (≤5k MAU) | Launch (≤50k MAU) | Growth (≤400k MAU) |
|------|----------------------|-------------------|--------------------|
| Vercel (web) | $20 (Pro, 1 seat) | $60 | $300 |
| ECS Fargate ARM (API, worker on Spot, fetcher 0→N) | $40 | $160 | $1,200 |
| ALB + public IPv4 | $35 | $50 | $150 |
| RDS PostgreSQL | $28 (t4g.small, single-AZ) | $120 (t4g.medium, Multi-AZ) | $900 (Aurora Serverless v2 / r7g + RDS Proxy) |
| ElastiCache Serverless (Valkey) | $10 | $30 | $150 |
| S3 + KMS + SQS + Secrets + ECR | $10 | $30 | $150 |
| CloudWatch + NAT (Growth only) | $15 | $50 | $400 |
| **AWS subtotal** | **~$160** | **~$500** | **~$3,250** |
| Sentry / Langfuse / PostHog | $0 (free tiers) | $150 | $900 |
| Resend (email), Cloudflare, status page | $0–20 | $60 | $250 |
| **Total infra + SaaS** | **~$200** | **~$700–1,200** | **~$4,500–6,000** |

On Groq, LLM spend is about **1–2× infra** at every stage (Base: ~$1.8k LLM vs. ~$1.2k infra), not the 3–10× it was on Claude. AWS cost floors to watch: a NAT gateway is ~$33/mo plus data, which is why it's deferred. Multi-AZ doubles RDS cost. Every public IPv4 address costs ~$3.65/mo.

---

## 5. Month-12 scenarios (plan G2: Quick free tier, Deep paid)

| | Conservative | Base | Viral |
|---|---|---|---|
| India MAU / paid conversion | 8,000 / 1.5% | 50,000 / 2% | 300,000 / 2% |
| US+global MAU / paid conversion | 3,000 / 4% | 15,000 / 5% | 80,000 / 5% |
| Paying users | 240 | 1,750 | 10,000 |
| **MRR** | **$2.8k** | **$18.4k** | **$100k** |
| Payment fees | $0.2k | $1.1k | $5.7k |
| LLM (Groq) | $0.3k | $1.8k | $10.6k |
| Infra + SaaS | $0.3k | $1.2k | $6.0k |
| **Gross profit (GM)** | **$2.0k (73%)** | **$14.3k (78%)** | **$78.1k (78%)** |
| ARR run-rate | $34k | $221k | $1.2M |

Revenue skews heavily to the US even when users skew to India: in Base, India is 77% of MAU but 18% of MRR. **India brings volume and virality; the US brings revenue.** That shapes the GTM in [ROADMAP.md](ROADMAP.md).

**Sensitivity:** the scenarios assume 5% free → paid in the US. The published HR-SaaS freemium average is **3.7%** (MARKET.md). At 3.7%, Base MRR drops from $18.4k to ~$14.5k. Treat Base as needing a good funnel, not an average one. A more generous free tier may lower conversion further, so watch it in beta. The $20 US ARPPU assumes a blend of Sprint passes, monthly and quarterly plans: check it against real purchase data after 4 weeks.

---

## 6. Startup costs beyond the product

### 6.1 One-time & annual (pick the entity path that matches the founders)

| Item | India-first | US (Delaware C-corp) |
|------|-------------|----------------------|
| Incorporation | Private Limited via SPICe+: ~₹8k–15k incl. professional fees | Stripe Atlas $500 (incl. first-year registered agent), or Clerky |
| Annual compliance | CA, ROC filings, GST returns: ~₹40k–90k/yr | Delaware franchise tax (~$400+ under the assumed-par method) + registered agent ~$100–300 + tax filing $1–3k/yr |
| Startup recognition | DPIIT Startup India (free; tax and IP benefits, cheaper trademark fees) | – |
| Trademark (1 class, class 42 or 9) | ~₹4,500 (startup/individual rate) | USPTO ~$350 per class (base application) |
| ToS + privacy policy | Generator (Termly/iubenda ~$10–30/mo), or a lawyer review ~₹25k–75k / $1–3k | same |
| Domain(s) | $15–60/yr | same |
| Chrome Web Store developer | $5 one-time | same |
| Google Play (only for a TWA/Android wrapper) | $25 one-time | same |
| Apple Developer (only for a native iOS share extension) | $99/yr | same |

### 6.2 Monthly tools (small team)
- Google Workspace (~$7/user)
- GitHub (free → Team $4/user)
- Figma (free → $16/editor)
- Claude subscriptions for building with Claude Code (Pro/Max, $20–$200/seat)
- **Groq API Developer tier**, pay as you go. Dev and evals cost ~$10–50/mo. A 12-case bake-off of two models with the judge is well under $1; `evals/run_eval.py --estimate` gives the exact figure.
- Linear or Notion (free tiers)

### 6.3 Credits to apply for (they lower months 1–12 a lot; check the current terms)
- **AWS Activate** (Founders tier, or a higher Portfolio tier through an accelerator or VC). Covers the AWS line.
- **PostHog for Startups**, **Sentry for Startups**, **Vercel for Startups**, **Microsoft for Startups**.
- Ask Groq about startup or enterprise programs (no credits assumed here).
- Indian programs: **Startup India Seed Fund**, state startup cells (Karnataka, Telangana T-Hub, Kerala KSUM), and university incubators.

### 6.4 People
| Option | Monthly |
|--------|---------|
| Founders unpaid; freelance designer for brand + 3 templates | $1.5k–4k one-time (India ₹60k–2L) |
| Recruiter or hiring-manager reviewers for evals (10 h/month) | $250–500 (India ₹8k–15k) |
| Campus ambassadors (India, during the season) | ₹2k–5k stipend each + packs |
| First hire: full-stack engineer | India ₹20–40 LPA (~$1.9k–3.8k/mo) · US $150k–200k/yr |

### 6.5 12-month budget (bootstrapped, founders unpaid, base scenario)

| Bucket | 12-month total |
|--------|----------------|
| Infra + SaaS (dev months ~$100, then ramping to ~$1.2k) | ~$6k |
| LLM: development + evals (Groq) | ~$0.5k |
| LLM: production not yet covered by revenue (beta and early launch) | ~$1k |
| Company, legal, trademark | ~$2–3k |
| Design (brand, templates, landing page) | ~$2–4k |
| Marketing (creators, ambassadors, ad tests, launch) | ~$9–15k |
| Tools & subscriptions | ~$1.5k |
| Contingency (15%) | ~$3–5k |
| **Total cash needed** | **≈ $25k–36k**, before credits (AWS credits can offset most of the infra line) |

Moving to Groq takes about $8–9k out of the 12-month cash need. **Marketing is now the biggest line by far.** A funded plan (2 founders paid + 1 engineer + 1 growth person) is ≈ $15k–25k/mo in India or $60k–90k/mo in the US, on top of this.

---

## 7. Reproducing the numbers

Every number in §1, §2 and §5 comes from [`docs/models/unit_economics.py`](models/unit_economics.py). On Windows, run `.venv/Scripts/python.exe docs/models/unit_economics.py`. Re-run it whenever prices, token budgets or conversion assumptions change. **Replace the §1.2 budgets with real `llm_calls` ledger medians as soon as the first bake-off has run.**
