---
name: jd-ingestion
description: How Tailor turns a job URL, pasted text, screenshots or a browser-extension payload into a JobSpec. Covers the source order (public ATS APIs, then JSON-LD, readable HTML, headless render, ask the user), URL patterns, client-only domains we never fetch server-side, fetcher sandbox rules (SSRF, timeouts), screenshot handling, caching and dedupe, and the JobSpec schema. Use when touching server/app/features/jobs/, the fetcher service, or the extension's page reader.
---

# Job Description Ingestion

Code: `server/app/features/jobs/ingestion/`. One adapter per source, all returning `RawJob { text, structured?, source, ats_vendor?, canonical_url? }`, which one structured LLM call (`jd_extract`) turns into a `JobSpec`.

## 1. Source order (the first success wins)

1. **Public ATS posting APIs** (structured, fast, published for this purpose):

| Vendor | URL signal | Endpoint |
|--------|-----------|----------|
| Greenhouse | `boards.greenhouse.io/{board}/jobs/{id}`, `job-boards.greenhouse.io/...`, `?gh_jid=` | `GET https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{id}` |
| Lever | `jobs.lever.co/{site}/{id}` | `GET https://api.lever.co/v0/postings/{site}/{id}` |
| Ashby | `jobs.ashbyhq.com/{board}/{id}` | `GET https://api.ashbyhq.com/posting-api/job-board/{board}` → select by id |
| SmartRecruiters | `jobs.smartrecruiters.com/{company}/{id}` | `GET https://api.smartrecruiters.com/v1/companies/{company}/postings/{id}` |
| Workday | `{tenant}.wd{N}.myworkdayjobs.com/{site}/job/...` | `GET https://{host}/wday/cxs/{tenant}/{site}/job/{path}` (the JSON the page itself loads) |

2. **schema.org `JobPosting` JSON-LD** in the HTML (`extruct`). Most career sites ship it for Google Jobs.
3. **Readable HTML** (`trafilatura`) when there's no JSON-LD.
4. **Headless render** through the isolated **fetcher** service (Playwright) when the page is JS-only.
5. **Ask the user:** "We couldn't read this page. Use the extension, paste the text, or add a screenshot."

Record `ats_vendor` whenever it's detectable: it drives template and format advice (see `ats-compliance`).

## 2. Client-only domains (never fetched by our servers)

`linkedin.com`, `indeed.*`, `naukri.com`, `glassdoor.*`, `monster.*`, `foundit.in`, `instahyre.com`, `wellfound.com`, plus any site that requires login or forbids automated access in its ToS. Keep the list in `ingestion/policy.py` (one source of truth, unit-tested).

For these:
- The **extension** reads the job panel from the DOM of the page the user is already viewing, and **only when the user clicks**. That's a single user-initiated read of visible content. No background crawling, no pagination, no reading of other users' data, no automated clicks or form actions.
- Or the user pastes the text or uploads screenshots.
- A URL on one of these domains returns a `ClientOnlySource` response, and the UI explains the alternatives in one line.

**Even the extension read is a terms-of-service grey zone on these sites.** LinkedIn's User Agreement §8.2 bans scraping "browser plugins and add-ons", and Indeed's Sep 2026 terms ban "AI or Agentic AI" bots. Large competitors operate there anyway, but:
- LinkedIn, Indeed and Naukri page readers ship **only after counsel review**;
- every site reader sits behind a **remote per-site kill switch** (a feature flag) that falls back to screenshot or paste mode without a new extension release;
- the extension's ATS-hosted readers (Greenhouse, Lever, Workday, Ashby, SmartRecruiters) are the launch set.

## 3. Fetcher sandbox rules

- A separate ECS service with no DB or S3 credentials. It receives a URL and returns HTML/text.
- **SSRF:** resolve DNS first, then block private, loopback, link-local and metadata ranges (`169.254.169.254`, `fd00::/8`, …); re-check after redirects; at most 3 redirects; http/https only.
- Limits: 10 s total, 3 MB body, no downloads, no cookies or storage persisted between jobs, a fresh browser context per job.
- Identify honestly with a User-Agent that includes a contact URL. Honor `robots.txt` for non-API fetches. Per-domain concurrency of 2.
- The output is untrusted data. It goes into the `jd_extract` prompt inside `<job_description>` delimiters only.

## 4. Screenshots

- At most 3 images per job, each downscaled to ≤1568 px on the long edge (≈ w×h/750 tokens each). Strip EXIF.
- They're sent in reading order in one call. The prompt asks the model to merge overlapping scroll captures and to say which fields were unreadable rather than guess.
- Typical source: LinkedIn/Naukri mobile apps on iOS (no Web Share Target there).

## 5. Caching & dedupe

- `canonical_url`: lowercase host, strip tracking params (`utm_*`, `gh_src`, `ref`, `trk`, `lever-source`), resolve known short links.
- Public-URL jobs are shared across users (`jobs.owner_user_id IS NULL`) and re-fetched only if older than 7 days and the user asks to refresh. Pasted text and screenshots are private (`owner_user_id` set). `content_hash` = sha256 of the normalized text, which dedupes identical reposts.
- A cache hit skips the fetch **and** the `jd_extract` call. Track the hit rate: during viral spikes, many users apply to the same few jobs.

## 6. JobSpec contract

The source of truth is `server/app/llm/schemas.py::JobSpec`, which the `jd_extract` step returns:

```
JobSpec:
  title, company?, location?, remote_policy (onsite|hybrid|remote|unknown), seniority, employment_type
  visa_sponsorship (yes|no|unknown), salary? {min, max, currency, period}
  requirements[]: {id "r1", text, kind: skill|tool|cert|degree|years|domain|language|other,
                   tier: basic|preferred, evidence_terms[]}       # basic = required; mirrors HiredScore/Ashby grading
  responsibilities[]: str
  keywords[]:    {term, synonyms[], weight 1–3}                    # exact JD spelling first
  company_signals[]: short facts from the JD usable in a cover-letter hook
  application_questions[]
  language, unreadable_fields[]                                    # never guess; list what couldn't be read
```
Ingestion metadata (`ats_vendor`, `source`, `canonical_url`, `content_hash`) lives on the `jobs` table, not in the LLM output.

Evals: keep ≥20 ingestion fixtures (saved HTML/JSON plus expected JobSpec) covering each adapter, a German JD, an Indian campus JD and a messy screenshot.
