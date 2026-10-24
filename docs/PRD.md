# PRD: "Tailor" (working name)

## 1. Problem

Job seekers send dozens to hundreds of applications. Tailoring each resume and cover letter takes 30–60 minutes, so most people send one generic resume. That resume then scores low in recruiter keyword searches and reads as generic in a 7-second skim. Generic AI tools (ChatGPT, Claude) can help, but they need prompt skill, fabricate experience, sound robotic, and produce text, not a parse-safe PDF.

## 2. Product promise

> **Share a job, get your application in under a minute:** a tailored resume that's truthful, sounds like you and parses cleanly, plus the cover letter and the messages to send.

Three things competitors don't do together, and we have to win on all three:
1. **Truthful by construction.** Every line is traceable to the user's real experience. Gaps get asked about, not invented.
2. **Instant from anywhere.** URL, screenshot, extension button or (later) WhatsApp. The first result shows within seconds.
3. **Proof, not promises.** "What the ATS sees" and requirement-by-requirement coverage, instead of a made-up "ATS score".

## 3. Target users (in priority order)

| Persona | Context | Job-to-be-done | Willingness to pay |
|---------|---------|----------------|--------------------|
| **P1: India early-career tech** (final-year students, 0–3 yrs) | Off-campus and campus drives; LinkedIn, Naukri, company portals; mobile-first; 50–300 applications per season | "Get shortlisted for more of the roles I apply to without rewriting my resume every time" | Low per user (₹99–₹499), very high volume |
| **P2: US new grads & international students** (F-1/OPT, H-1B transfers) | High-volume applications, sponsorship filters, career-fair deadlines | "Apply to 20 good-fit jobs this week with materials that don't look copy-pasted" | Medium ($10–$30/mo during the search) |
| **P3: Laid-off / mid-career tech workers** (US, India, UK) | Quality over volume, referral-driven, need outreach | "Tailor fast and reach the hiring manager or a referral" | High ($20–$40/mo) |
| **P4: Career switchers & non-tech** (nurses, sales, ops, teachers → tech) | Experience must be translated into the target role's language | "Make my experience make sense for this role, honestly" | Medium |

**Beachhead:** P1 + P2 (the most volume, the most social sharing, a shared campus calendar). P3 is the revenue engine once the product is polished.

## 4. Scope by phase

### Phase 1: MVP (weeks 3–8)
| Feature | Acceptance criteria |
|---------|---------------------|
| Sign up | Google / LinkedIn OAuth + email magic link. ≤ 2 clicks to start |
| Resume onboarding | Upload PDF/DOCX/image or paste text → profile parsed in ≤ 20 s → user reviews it on one screen → 3–5 enrichment questions (skippable) |
| Job intake | URL (ATS APIs / JSON-LD / HTML), pasted text, 1–3 screenshots. Client-only domains explain how to use the extension, paste or screenshot instead |
| Free match scan | Base resume vs. job: requirement checklist (✓ evidenced / ~ partial / ✗ gap), keyword coverage, ATS parse check of the *current* resume. ≤ 8 s |
| Tailored resume | Streamed generation. PDF and DOCX download, 2 ATS-safe templates (Classic, Modern), page size set by region, fit-to-page |
| Diff review | Per bullet: base vs. tailored, the reason it changed, accept/reject. Inline edit. Truthfulness flags shown |
| Cover letter + outreach | Cover letter, recruiter email, LinkedIn note, referral ask, follow-up. Copy buttons, plus the cover letter as PDF/DOCX |
| Application list | Every job with its materials, status (draft/applied/interview/offer/rejected), re-download |
| Billing | Free tier + Pro (monthly and weekly pass). Stripe (international) and Razorpay (India, UPI) |
| Account | Export my data, delete my account, retention setting for raw uploads |

### Phase 2: Distribution & retention (weeks 9–14)
- **Chrome extension:** a "Tailor this job" button on Greenhouse, Lever, Workday and Ashby pages (and on LinkedIn, Indeed and Naukri once counsel has reviewed their terms; see MARKET §6). On click, it reads only the visible job panel and opens a side panel with the match report and a Generate button.
- **Shareable match card:** "Matched 11/12 requirements for Data Analyst @ X" as an image for LinkedIn or Instagram, with no PII by default and a referral link.
- **Referral program:** give 5 tailored packs, get 5 tailored packs.
- **Editor copilot:** natural-language edits ("one page", "more senior", "emphasize leadership").
- **Gap interviewer** in the generation flow.
- **Application-question answers:** "Why do you want to work here?" style answers from the profile and the JD.

### Phase 3: Channels & depth (months 4–6)
- **WhatsApp bot** (India): forward a job link or screenshot and get the PDF back in chat. Uses WhatsApp Cloud API service conversations.
- **PWA share target** polish plus a mobile-first flow. An iOS share extension if the data justifies it.
- **Interview prep pack:** likely questions from the JD, plus STAR stories from the profile.
- **Outcome tracking:** reminders to update status, and interview-rate stats per user ("your tailored applications got 3× more callbacks").
- Programmatic SEO pages ("[Role] resume example for [Company]") built from aggregated, anonymized JobSpecs.
- More templates; UK/EU/Gulf conventions; German-language output.

### Phase 4: Platform (months 6–12)
- Job recommendations ("jobs you match 80%+"). This is where pgvector comes in.
- **Assisted apply:** autofill application forms from the profile, with the user reviewing every submit. **Never blind auto-apply.**
- **B2B2C:** universities' placement cells, bootcamps and outplacement firms buy seats with an admin dashboard.

## 5. Non-goals (deliberate)

- **Mass auto-apply bots.** They spam recruiters, get accounts banned, and burn the brand. We help people apply *better*, not just *more*.
- **Fabrication features** ("add skills I don't have", hidden keywords, white text).
- **Claims of guaranteed ATS pass or interviews.**
- A recruiter-side product in year 1 (different buyer, and high-risk under the EU AI Act).

## 6. Key user flows

**First-time user (target: first pack downloaded within 3 minutes of landing):**
Landing ("Paste a job link") → paste a job → free match scan with the base resume (resume upload prompted inline) → sign up with Google to see the full report → Generate → stream → review the diff → download (paywall after the free allowance).

**Returning user:** Extension button on a job page → side panel match report → Generate → download → mark applied.

**Mobile (Android):** LinkedIn app → Share → Tailor PWA → match report → Generate → download or share the PDF.
**Mobile (iOS):** Screenshot the job → open Tailor → upload the screenshots.

## 7. Pricing (detail and rationale in [COSTS.md](COSTS.md#3-pricing))

Two generation modes on Groq ([ADR-0001](adr/ADR-0001-llm-provider-groq.md)): **Quick** (gpt-oss-20b, ≤10 s) and **Deep** (gpt-oss-120b, ≤20 s, with a stronger rewrite and the verifier loop). Both cost cents per pack, so the free tier can be monthly. See COSTS §2.

| Plan | US / global | India | Includes |
|------|-------------|-------|----------|
| Free | $0 | ₹0 | Unlimited match scans (fair use), **3 Quick packs per month**, +3 per referral, 1 Deep pack at signup |
| Sprint pass | $12 / 7 days, **one-time** | ₹149 / 7 days, one-time | Quick + Deep, unlimited packs (fair use 100), all templates, cover letters and outreach |
| Pro monthly | $24 / month | ₹399 / 30 days (UPI one-time or opt-in Autopay) | Sprint + tracker, interview prep (Phase 3), priority speed |
| **Pro quarter** (anchor) | $59 / 90 days | ₹999 / 90 days | Same as Pro monthly |
| Credit pack (India) | — | ₹99 for 10 Deep packs | No subscription, for price-sensitive users |

**Billing promises (part of the brand, not just policy):** no card-up-front trials, one-click cancel, a reminder before every renewal, a 7-day refund on first purchases. Competitors' 2.0–2.9 Trustpilot scores come mostly from billing traps (MARKET.md §1).

*The Phase 0 bake-off decides whether Quick (20b) holds the hard gates. If it doesn't, the free tier runs on 120b too: still about 70% gross margin (COSTS §2).*

## 8. Success metrics

| Layer | Metric | Target (first 6 months after launch) |
|-------|--------|---------------------------------------|
| North star | **Tailored packs downloaded per week** | Week-on-week growth ≥ 10% |
| Outcome (quality truth) | Self-reported interview rate per 100 tailored applications vs. the user's untailored baseline | ≥ 1.5× baseline |
| Activation | Signup → first pack downloaded in the same session | ≥ 40% |
| Speed | Time from job intake to resume PDF, p50 / p95 | ≤ 25 s / ≤ 45 s |
| Monetization | Free → paid conversion (30-day) | 3–6% globally, 1.5–3% India |
| Virality | K-factor (invites × conversion) from referrals + share cards | ≥ 0.3 (≥ 0.5 during campus season) |
| Retention | Active-seeker W4 retention (users still searching) | ≥ 35% |
| Trust | Fabrication incidents reported per 10k packs | < 1 (and every one becomes an eval case) |
| Unit economics | LLM cost per pack (p50) | Within the target in COSTS.md for the plan tier |

Churn after someone lands a job is *good churn*: track "landed a job" as an outcome, ask for a testimonial, and offer an alumni plan for the next search.
