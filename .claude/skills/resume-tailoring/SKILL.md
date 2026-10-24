---
name: resume-tailoring
description: Domain rules for what Tailor writes. Covers the truthfulness boundary (allowed vs. forbidden transformations), resume structure by career stage and region, bullet anatomy, keyword integration, human voice and the banned-phrase list, and cover letter / recruiter email / LinkedIn note / referral ask / follow-up formats. Use when writing or reviewing prompts, linters, eval graders, templates or any generated application content.
---

# Resume Tailoring: Domain Rules

These rules are the product. They are compiled into the global system prompt (`server/app/llm/prompts/_global_policy.md`), enforced by deterministic linters (`server/app/llm/style/`), and graded by the eval set. When this file changes, update all three.

**The reader:** a recruiter skimming for about 7 seconds (Ladders eye-tracking study, 2018), then a hiring manager reading closely, with an ATS parsing and keyword-matching both of them. Write for all three: the top third makes the fit obvious, every line survives a "prove it" question in the interview, and the text parses cleanly.

---

## 1. The truthfulness boundary (hard rules)

| Allowed (the tailoring is in these) | Forbidden (never, even if the user asks in the copilot) |
|------------------------------------------|----------------------------------------------------------|
| Select, reorder and merge facts by relevance to the JD | New employers, titles, dates, degrees, certifications |
| Rephrase in the JD's terminology when it names *the same thing* ("built REST services" → "designed RESTful APIs") | Upgrading a title ("Engineer" → "Senior Engineer", "helped lead" → "led") |
| Surface a skill a fact clearly shows (a fact about writing Terraform → the skill "Terraform") | Inflating numbers, scope, team size, revenue, users |
| Use numbers that are in the source facts, including converted forms (40% → "cut by 40%") | Adding a skill or tool with no supporting fact or user confirmation |
| Change the summary's angle to match the target role | Swapping in a "similar" tool (BigQuery ≠ Redshift, Vue ≠ React) |
| Drop irrelevant content to fit the page limit | Hidden or white text, keyword dumps, copying JD sentences verbatim |
| Ask the user about a gap and add their answer as a new fact | Implying a gap is covered when it isn't |

Every bullet and skill in the output cites `source_fact_ids`. If a must-have can't be evidenced, it's **left out and reported as a gap**, with an honest next step (a quick project, a certification, or how to address it in the cover letter).

---

## 2. Structure

### By career stage

| Stage | Section order | Notes |
|-------|---------------|-------|
| Student / fresher (0–1 yr) | Header → Summary (optional, 2 lines) → Education → Projects → Internships/Experience → Skills → Achievements/Certifications | India campus hiring: show CGPA (and 10th/12th % only if the JD or college asks). Projects carry the weight: tech, what it does, a measurable outcome (users, stars, latency, rank) |
| Experienced (2+ yrs) | Header → Summary → Experience → Skills → Projects (if relevant) → Education → Certifications | Education goes below experience. Graduation year is optional after ~10 yrs |
| Career switcher | Header → Summary (transferable framing) → Relevant Projects/Experience → Other Experience (condensed) → Skills → Education/Training | Lead with evidence for the *target* role, wherever it came from |
| Senior / leadership | Header → Summary → Experience (scope: team size, budget, outcomes) → Board/Advisory → Education | Two pages is normal |

### By region (defaults; the user can override in preferences)

| Region | Name | Length | Photo / personal data | Spelling | Notes |
|--------|------|--------|-----------------------|----------|-------|
| US | Resume | 1 page < ~8–10 yrs, else 2 | No photo, DOB, marital status or full address (city + state is enough) | en-US | |
| Canada | Resume | 1–2 | Same as US | en-CA / en-US | |
| UK / Ireland | CV | 2 | No photo or DOB | en-GB | "CV" in file name and copy |
| India | Resume / CV | 1 for freshers, 1–2 experienced | No photo for MNC/tech roles. Omit DOB, marital status, father's name and the "Declaration" section | en-IN (British spelling) | Notice period and current location are useful when the JD mentions them |
| Germany / DACH | Lebenslauf / CV | 1–2 | A photo is still common but optional. Follow the user's preference | Per the language of the posting | If the JD is in German, ask before writing in German |
| Gulf (UAE, KSA) | CV | 2 | Nationality and visa status are common. A photo is common | en-GB | |
| Australia / NZ | Resume | 2–3 | No photo | en-AU | |

Always remove: "References available upon request", objective statements (replaced by the summary), multiple phone numbers, and full street addresses.
**Special-category and sensitive data** (photo, date of birth or age, religion, caste, health or disability, marital status, father's or spouse's name, nationality where irrelevant) is stripped from generated output by default. It's kept only when the user explicitly opts in for a region where it's expected (e.g. a photo for DACH, nationality or visa for the Gulf). This is GDPR Art. 9 hygiene and good resume practice.
Date format: `Mon YYYY – Mon YYYY` / `Mon YYYY – Present`, used consistently.

---

## 3. Bullet anatomy

**Action + what + how/tools + result.** Use a number when the source has one.
- Formula: *Accomplished [X] as measured by [Y] by doing [Z]*. Results first when the result is strong.
- Length: 1–2 lines (~14–28 words). Recent role: 3–6 bullets; older roles: 1–3.
- Order bullets inside a role by relevance to the JD's must-haves, not by chronology.
- No pronouns. Past tense for past roles, present tense for the current role.
- Each bullet starts with a different verb within a role. Plain, specific verbs beat inflated ones: *built, shipped, cut, grew, ran, wrote, fixed, migrated, negotiated, sold, taught, designed, automated, launched, reduced, led* (only when the person actually led).

| Weak | Strong (only if the facts support it) |
|------|---------------------------------------|
| Responsible for backend services | Built 6 Go microservices handling 2M payment events/day on Kafka and Postgres |
| Spearheaded cross-functional synergy to leverage data | Ran weekly reviews with sales and support, which cut ticket backlog from 400 to 90 in 2 months |

---

## 4. Keyword integration (ATS + recruiter search)

- Use the **JD's exact spelling** for must-have terms where truthful. Many ATS and recruiter searches match literally ("Kubernetes", not only "K8s").
- Write the expansion and the acronym once: "Search Engine Optimization (SEO)".
- Each must-have keyword should appear in **Skills and in at least one experience or project bullet** (keywords in context rank better and survive a human read).
- Group the skills section (Languages · Frameworks · Cloud/Infra · Data · Tools). No more than ~25 items. No proficiency bars or graphics.
- No keyword stuffing: a term appears at most ~3 times. Never copy JD sentences.

---

## 5. Summary (2–3 lines)

Target role language + years + core specialty + 1–2 proof points + (optional) what you're looking for. No "I", no clichés.
> Backend engineer with 5 years building payment systems in Go and Kafka; cut settlement latency 60% at 10M transactions/day. Looking for platform roles in fintech.

---

## 6. Human voice

The aim is writing that sounds like a sharp version of the user, not "undetectable AI". AI-detector scores are unreliable and are not a goal.
- **Match the StyleProfile:** the user's typical bullet length, how they write numbers, their verb habits. Stay recognizably *them*.
- **Vary rhythm:** mix short and long bullets, and don't start three bullets in a row the same way.
- **Be specific:** names of systems, real numbers, real constraints. Specificity is what makes text read as human.
- **Banned patterns:** em-dash chains; "not only… but also"; triads in every sentence ("fast, reliable, and scalable"); rhetorical openers; adverb padding ("successfully", "effectively", "seamlessly").

### Banned phrases (initial list; mirrored in `server/app/llm/style/banned_phrases.txt` once that exists)

spearheaded · leveraged (as filler) · utilized (→ used) · results-driven · detail-oriented · team player · self-starter · go-getter · hard-working · passionate about · dynamic · synergy · proven track record · think outside the box · best-in-class · cutting-edge · world-class · seamless(ly) · robust (unless a technical property) · delve · tapestry · testament to · pivotal · meticulous(ly) · honed · adept at · orchestrated · navigate the complexities · embark · unlock · empower · elevate · foster · harness · in today's fast-paced · ever-evolving landscape · plays a crucial role · I am writing to express my interest · I believe I would be a great fit · thrilled · perfect fit · "Furthermore," / "Moreover," / "Additionally," (at most 1 per letter)

The linter fails the Verifier step on any hit in the resume. For letters it allows ≤1 soft hit (the connector words) and 0 others.

---

## 7. Cover letter (250–350 words, 3–4 short paragraphs)

1. **Hook (2–3 sentences):** the role, plus one *specific* thing about the company or team taken from the JD or company signals (a product, a problem they named, a stack choice). Never "I'm excited to apply to this amazing opportunity".
2. **Proof (1–2 paragraphs):** two short stories that map to the JD's top two requirements, each with a number. Don't restate the resume line by line.
3. **Why here / fit (1–2 sentences):** concrete and honest. If there's an addressed gap ("I haven't used Kafka in production; I've built X with RabbitMQ and am …"), it goes here.
4. **Close:** a clear, low-pressure ask ("Happy to walk through the settlement redesign in a call").
- Salutation: the hiring manager's name only if the JD or the user supplied it. Otherwise "Dear Hiring Team,". **Never invent a name.**
- Sign-off uses `{{FULL_NAME}}`. Same spelling variant as the resume.

## 8. Outreach pack

| Piece | Limits | Shape |
|-------|--------|-------|
| Recruiter / hiring-manager email | ≤120 words; specific subject ("Backend Engineer, Payments: 5 yrs Go/Kafka") | 1 line on who you are and the role → 2 proof points → the ask → links |
| LinkedIn connection note | ≤200 characters (fits free accounts) | Role + one specific hook + a soft ask. No attachments, no "please refer me" in the first message |
| Referral ask (to a contact at the company) | ≤100 words | Job link or ID, a 2-line pitch, an offer to send the resume, and an easy out ("totally fine if not") |
| Follow-up (7–10 days after applying) | ≤80 words | Reference the application date and role, add one new data point, restate interest |

Never fabricate a mutual connection, a referral or prior contact.
