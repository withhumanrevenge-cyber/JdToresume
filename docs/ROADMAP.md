# Roadmap: from idea to a deployed, growing product

Each phase has **exit criteria**. Don't start the next phase on calendar time alone. Team assumption: 1–2 technical founders using Claude Code with the subagents in `.claude/agents/`, plus a part-time designer.

---

## Phase 0: Validate & de-risk (weeks 0–2)

The goal is to answer the three questions that can kill the business before building it.

| Question | How | Pass bar |
|----------|-----|----------|
| Do people want it enough to pay? | 20 interviews (10 India early-career, 5 US new-grad or international students, 5 laid-off mid-career) + a **concierge test**: generate packs with the Phase 0 pipeline (`app.features.generation.pipeline`) and review each one by hand, for 30 real job seekers over 2 weeks | ≥ 40% say they'd pay at the planned price; ≥ 10 pre-orders or deposits |
| Is the output better than they could do themselves? | Blind test: their own resume vs. our tailored one, rated by 5 recruiters or hiring managers | Ours preferred in ≥ 70% of pairs; **0 fabrications** |
| Can open models on Groq write well enough without fabricating? ([ADR-0001](adr/ADR-0001-llm-provider-groq.md)) | Eval set v0 (12 cases now, growing to 60 from concierge users) + a bake-off with `evals/run_eval.py`: gpt-oss-120b vs gpt-oss-20b (vs qwen3.8-27b, preview), plus the pairwise judge. Under $1 per run | 120b: fabrication = 0 and recruiters prefer its output over the candidate's original in ≥ 70% of blind pairs. 20b keeps Quick mode only if it also has fabrication = 0 and wins or ties ≥ 40% against 120b |

Also in Phase 0:
- [ ] Landing page + waitlist ("Paste a job link, get a tailored resume in 30 s"). Target: 1,000 signups from founder LinkedIn posts, 2 campus groups and 1 subreddit.
- [ ] Prototype Typst templates (Classic, Modern) + the ATS round-trip script. Test them against 10 real ATS uploads (create applications on public Greenhouse/Lever/Workday postings you'd actually apply to, or ask friends at companies to check the parsed view).
- [ ] Pick the working name, and run a domain + trademark search (`.com` / `.ai` / `.in`).
- [ ] **Founder decisions:** entity country, launch market, model mix, name (see "Decision gates" at the end).

---

## Phase 1: MVP build (weeks 3–8)

Built with: `architect` → `engineer` → `reviewer` per feature, and `prompt-engineer` for every pipeline step.

| Week | Deliverables |
|------|--------------|
| 3 | Monorepo + CI (GitHub Actions) · Terraform skeleton (network, ECS, RDS, S3, SQS) · local docker-compose · auth (Better Auth: Google, LinkedIn, magic link) · presigned uploads |
| 4 | Resume parser → career profile v1 + profile review screen · contact-detail placeholder layer + test · `llm_calls` ledger + budget guard |
| 5 | JD ingestion: ATS APIs, JSON-LD, HTML, screenshots, client-only policy · JobSpec cache · free match scan endpoint + UI |
| 6 | Pipeline DAG: match → tailor → verify → revise · SSE streaming + the `useGenerationStream` hook · checkpointing and resume |
| 7 | Typst renderer + fit-to-page + DOCX · ATS round-trip check · diff review UI · "What the ATS sees" |
| 8 | Cover letter + outreach · billing (Razorpay + Stripe or MoR), entitlements, metering · account export/delete · Sentry/Langfuse/PostHog · **closed beta (100 users from the waitlist)** |

**Exit criteria → Phase 2:** activation ≥ 30% · p50 time-to-PDF ≤ 30 s (Deep) / ≤ 12 s (Quick) · fabrication 0 in 200 audited beta packs (`resume-auditor`) · ≥ 20 paying beta users · LLM cost per pack within 20% of COSTS §1.

---

## Phase 2: Distribution & public launch (weeks 9–14)

| Item | Notes |
|------|-------|
| Chrome extension (WXT) | Page readers + side panel. Launch on **Greenhouse, Lever, Workday and Ashby** pages. LinkedIn, Indeed and Naukri are added **only after counsel review**, in click-to-read mode with a per-site kill switch. **Submit to the Chrome Web Store in week 10**: reviews can take days to weeks, and the listing copy must follow `ats-compliance` §5 |
| Shareable match card | No PII by default, with a referral link. Formats sized for LinkedIn, Instagram story and WhatsApp status |
| Referral program | +3 Quick packs for both sides (+1 Deep pack for the referrer). Fraud checks: same device, IP or payment method |
| Editor copilot + gap interviewer | Agentic steps, with eval cases |
| "Tailor this job" deep links | `tailor.app/j?u=<job url>` that job-alert channels and creators append to their posts (see GTM) |
| Public launch | Product Hunt (Tuesday–Thursday), founder LinkedIn launch post, campus ambassadors live, Reddit (follow each subreddit's self-promotion rules), Hacker News "Show HN" only if there's a technical story (e.g. the ATS round-trip tool, open-sourced) |

**Exit criteria → Phase 3:** 10k MAU · K-factor ≥ 0.3 · free→paid ≥ 2% blended · W4 active-seeker retention ≥ 30%.

---

## Phase 3: Channels & depth (months 4–6)

- **WhatsApp bot (India):** forward a job link or screenshot → get the match summary and the PDF in chat. User-initiated service conversations keep the per-message cost low. Tie it to the account by phone number with OTP.
- **Interview prep pack** (likely questions from the JD plus STAR stories from the profile) as an upsell in Pro.
- **Outcome tracking:** status nudges and "your tailored applications got N× more callbacks", the data flywheel and the best marketing proof.
- **Programmatic SEO + free tools:** "ATS resume checker", "resume keyword scanner", "cover letter generator", and role × company pages from aggregated, anonymized JobSpecs. Free tools rank well, and they're the scan funnel.
- Regions: UK CV and Gulf conventions, A4 templates, German output (if EU demand shows up in the data).

## Phase 4: Platform & scale (months 6–12)

- Job recommendations ("jobs you match 80%+": pgvector, with an ADR first).
- **Assisted apply:** autofill forms from the profile, with a human review of every submit. Never blind auto-apply.
- **B2B2C pilots:** 3 colleges, placement cells or bootcamps (India), 1–2 US career centers or outplacement firms. Seat-based pricing and an admin dashboard. This smooths out consumer seasonality.
- Fundraise if the metrics support it (see the scenario model in COSTS §5), or stay profitable and bootstrapped.

---

## Go-to-market

### Markets (detail in [MARKET.md](MARKET.md))
- **India = volume and virality.** The highest density of job seekers in shared channels (campus groups, Telegram/WhatsApp job-alert channels, LinkedIn). Price-sensitive; UPI is essential.
- **US/global = revenue.** ~5× the ARPPU. New grads and international students are the reachable beachhead; laid-off tech workers have the highest willingness to pay.
- **Plan:** launch in English globally on day one with market-specific prices, and focus *marketing effort* on India for growth loops and on US students for revenue.

### Calendar effects
- India campus placement season: roughly **Jul–Dec** (with off-campus hiring continuing into spring). Ambassador onboarding in June–July.
- US: **Aug–Oct** (fall recruiting for new grads), **Jan–Mar** (spring hiring), plus spikes after big layoff announcements.
- January is the classic "new job" resolution spike across all markets.

### Beachhead for paid conversion
**Indian international students and new grads in the US** (F-1/OPT, H-1B transfers). They pay US prices, face the hardest search (sponsorship), cluster in campus clubs and WhatsApp groups, and carry the product back into Indian networks. That makes them the bridge between the revenue market and the virality market (MARKET.md §5.4).

### Growth loops (ranked by expected impact; the evidence for each is in MARKET.md §5)
1. **"Tailor this job" links inside job feeds:**
   - **US:** maintain open GitHub/Notion new-grad and internship lists (Simplify's repo has 48K stars), including an "H-1B-sponsoring roles" list.
   - **India:** partner with Telegram/WhatsApp job-alert channels and LinkedIn job-posting creators.

   Every listing carries a deep link to a free scan on that exact job. Channel owners get a revenue share or free Pro.
2. **Free scan → share card → referral.** "11/12 requirements matched" is a brag that recruits friends who are applying to the same jobs.
3. **Chrome extension on job pages:** Greenhouse, Lever, Workday and Ashby first; LinkedIn and Naukri in ToS-cautious mode (see the legal checklist). Category leaders get 60–66% direct traffic from their extensions.
4. **Campus ambassadors** (India, US career clubs): a stipend plus Pro, with leaderboards during placement season.
5. **SEO free tools** (from Phase 3): "see what the ATS reads", JD keyword gap. Resume Worded gets ~65% of its traffic from organic search.
6. **Founder-led content:** build-in-public posts, and "we parsed 10,000 resumes: here's what ATSs actually read" data posts (aggregated and anonymized).

---

## Legal & compliance checklist

| When | Item |
|------|------|
| Before beta | ToS + privacy policy (sub-processors: Groq, AWS, Vercel, payment provider, PostHog, Sentry) · Groq Zero Data Retention enabled on the production project · consent checkbox at resume upload · data export and delete working · **minimum age 18** in the ToS and at signup (DPDP requires verifiable parental consent for under-18s, and some first-year students are 17) |
| Before beta | No claims of guaranteed ATS pass, "3× interviews" or "undetectable" anywhere: the site, extension listing, ads, creator briefs. The FTC has acted on unsupported AI claims, and "undetectable" also conflicts with EU AI Act Art. 50 |
| Before beta | Special-category data: detect and strip photos, health, religion, caste, marital status and date of birth from generated output by default (GDPR Art. 9; it's also a resume best practice). Keep them only if the user explicitly opts in |
| Before charging | Entity, bank account, payment provider KYC · GST registration (India) or a sales-tax approach / MoR · **billing that complies with auto-renewal laws** (California ARL as amended Jul 2025: express consent, online one-click cancel, renewal reminders, consent records) · 7-day refund on first purchases |
| Before India scale | **DPDP Act + Rules 2025** (main obligations from **13/14 May 2027**; build to them now): notice and consent records, a grievance contact (90-day response), a breach process (notify the Board and affected users, with a detailed report within 72 h), **≥1 year of log retention**, erasure with a 48 h warning, a retention schedule |
| Before EU marketing | GDPR basics: DPA with vendors, SCCs as a fallback to the EU-US Data Privacy Framework, cookie consent for analytics, an EU representative if required. EU AI Act: a candidate-side tool is likely not Annex III high-risk, but get **counsel's view on Art. 50 machine-readable marking of AI-generated text** (live since 2 Aug 2026; systems already on the market have until 2 Dec 2026) and on whether the "assistive editing" exception covers tailoring. Never sell candidate scores to employers (that would trigger high-risk) |
| Extension launch | **Counsel review of LinkedIn User Agreement §8.2 and Indeed's Sep 2026 terms** (both ban scraping plugins and AI bots). Read only the visible job panel, only on an explicit click, never automate actions; ship a remote per-site kill switch that falls back to screenshot or paste mode. Chrome Web Store privacy disclosures. Apply for Indeed's "Permitted AI Connector" beta |
| Ongoing | Trademark filing once the name is final · annual compliance (ROC/CA in India, Delaware franchise tax in the US) |

---

## Risks & mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Commoditization: **already happening**. ChatGPT's resume editor (Jun 2026), Indeed Career Scout, Naukri Pro AI Resume Maker, LinkedIn Premium | High | High | Win on the full workflow (intake anywhere → PDF that parses → letters and outreach → tracker), on truthfulness and on speed. Own the career profile and the outcome data. Be where users already are (the extension, WhatsApp) |
| LinkedIn, Indeed or Naukri terms are enforced against the extension (LinkedIn UA §8.2 bans scraping plugins; Indeed's terms ban AI bots), or users' accounts get restricted | Medium | Medium–High | Counsel review before launch; read only on a click, visible job panel only, no automated actions; a remote per-site kill switch → screenshot or paste mode. Lead with ATS-hosted pages (Greenhouse, Lever, Workday, Ashby), which are fine to read |
| Billing-trust backlash (the category's 2.0–2.9 Trustpilot scores; auto-renewal lawsuits against Bold) | Medium | High | One-time passes, one-click cancel, renewal reminders, consent records, quick refunds. Make trust a visible part of the brand |
| LLM costs exceed plan (usage spikes, abuse) | Medium | High | Groq pricing (~$0.017/pack), budget guards, per-user ceilings, Quick (20b) scans, cached JobSpecs, daily spend alarms |
| Quality incident (a fabricated claim gets a user embarrassed in an interview) | Low–Medium | Very high | Provenance per bullet, the Verifier, fabrication = 0 gate, diff review before download, in-product reporting → eval case |
| Recruiter backlash against AI-written applications | Medium | Medium | Human voice from the user's style, no auto-apply spam, specificity over volume. Position as "better applications", not "more applications" |
| Seasonality and good churn (users leave once hired) | High | Medium | Weekly passes, alumni re-activation, B2B2C seats, career-profile upkeep reminders |
| Rate limits during a viral spike | Medium | Medium | Groq limit increases ahead of launches (base limits can't fit one request), a queue with a waiting room, other gpt-oss hosts as overflow (same prompts), Quick mode as the degradation path |
| Data breach (resumes are PII) | Low | Very high | Encryption, least-privilege IAM, no contact info sent to the LLM, retention limits, a pen-test before scale, an incident runbook |
| Payment friction in India (international cards, recurring mandates) | Medium | Medium | UPI one-time credit packs and weekly passes alongside subscriptions |

---

## Decision gates (founder decisions, with my recommendation)

| Decision | Recommendation | Decide by |
|----------|----------------|-----------|
| Launch market focus | **India for growth loops + US/global for revenue**, with one English product and per-market pricing. First paid beachhead: Indian international students in the US | End of Phase 0 |
| Entity | Where the founders live and bank. An India Pvt Ltd + MoR for international sales is the simplest start for India-based founders. A Delaware C-corp if raising from US investors soon | Before charging |
| Quick-mode model | gpt-oss-20b **if** it passes the bake-off gates; otherwise 120b for everyone (still ~70% GM) | End of Phase 0 |
| Deep-mode model | gpt-oss-120b, unless qwen3.8-27b (preview, ~5× the cost) clearly wins the judge and recruiter review. Model churn risk: re-run the bake-off whenever Groq's catalog changes | End of Phase 0 |
| Pricing | As in COSTS §3, re-tested after 4 weeks of beta conversion data | End of Phase 1 |
| Name and brand | Pick one that works in the US and India, with `.com` or `.ai` available. Use the `brand` and `design` skills for identity once chosen | Phase 0 |
| Funding | Bootstrapped to ~$20k MRR is plausible (COSTS §5 Base). Raise if the Viral-scenario signals show up (K ≥ 0.5, 100k MAU) | Phase 3 |

---

## Launch-readiness checklist (end of Phase 2)

- [ ] p95 time-to-PDF under target. Load test at 10× the expected peak (the queue and waiting room work)
- [ ] Groq rate limits raised for launch traffic. Overflow path tested. Zero Data Retention on
- [ ] Daily LLM spend alarm + per-user ceilings live
- [ ] Fabrication = 0 on the full eval set and on the last 500 audited beta packs
- [ ] Backups restored in a drill. Alembic rollback tested
- [ ] Status page, support inbox, refund flow
- [ ] Privacy policy, ToS, DPDP notice, cookie consent (EU) published
- [ ] Extension approved in the Chrome Web Store
- [ ] Analytics funnel verified end-to-end (landing → scan → signup → pack → pay → share)
