# Concierge test playbook (30 users, 2 weeks)

**Goal:** prove the output gets people **more interviews**, with zero fabrication, before building the product UI. We run the real pipeline (`app.features.generation.pipeline`) and review every pack by hand before it goes to the user.

## 1. Recruit and consent
- Source: interview "yes" answers plus their referrals. Mix: 15 India, 10 US/intl, 5 laid-off mid-career.
- Before taking a resume, send a short consent note and get a "yes" in writing:
  - what we store (resume, job posts, generated files), where (your machine + Groq for processing; contact details are removed before anything is sent to Groq), and for how long (deleted 30 days after the pilot unless they ask to keep it);
  - that outputs are drafts they must review;
  - that anonymized excerpts may become eval cases **only if they opt in** (a separate checkbox).
- Pilot price: ₹199 / $9 for 5 tailored packs (refundable). Payment is the signal, not the revenue.

## 2. Intake (per user)
1. Their current resume (PDF, or text/markdown).
2. 5 jobs they're about to apply to: links (we copy the text from the page ourselves) or screenshots.
3. Their baseline: applications and interviews in the last 30 days.

## 3. Produce each pack
1. Parse the resume into a profile and review it with the user: fix wrong dates and missing facts, and ask about their metrics. **The profile review is where most of the quality comes from.**
2. Run the pipeline for each job (the concierge script lands with the renderer; until then, use `generate_pack` from a Python shell).
3. **Hand review, using the `resume-auditor` checklist, before sending:**
   - [ ] Every bullet is true to the profile (no traps, no inflated scope or numbers).
   - [ ] The ATS round-trip passes (the "What the ATS sees" text looks right).
   - [ ] The cover letter has a specific hook, and outreach is within the length limits.
   - [ ] Log every fix you had to make: **each fix is a prompt bug and becomes an eval case.**
4. Send the PDF, the cover letter and the messages. Ask them to review before applying.

## 4. Measure (per user, a shared sheet)
| Field | When |
|-------|------|
| Baseline interviews / applications (30 days) | Intake |
| Packs delivered, time spent on review (min), # fixes per pack, fix types | Per pack |
| Applied with our pack? (Y/N) · edits they made themselves | +2 days |
| Responses / interviews from tailored applications | +7 and +14 days |
| "Would you pay [price] per month to keep this?" + the actual purchase | +14 days |

## 5. Pass bars (feed into ROADMAP Phase 0 exit)
- **0 fabricated claims** in delivered packs (fixes made before delivery are counted separately as prompt bugs).
- Interview rate on tailored applications ≥ 1.5× the user's own baseline (directional at this sample size; Huntr's public data shows ~1.85×).
- ≥ 40% of pilot users buy at the planned price at day 14.
- Median hand-review time per pack < 10 minutes. Above that, the prompts need work before the product.

## 6. Turn learnings into the product
- Every hand fix → a new eval case or grader rule in `evals/` (synthetic or anonymized, opt-in only).
- Re-run `evals/run_eval.py` after each prompt change, and compare reports.
- Delete pilot data on schedule. Keep only opted-in, anonymized eval cases.
