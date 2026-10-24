---
name: ats-compliance
description: How applicant tracking systems actually parse and search resumes, ATS-safe template rules for Typst/DOCX output, the deterministic round-trip check, vendor notes (Workday, Greenhouse, Lever, iCIMS, Taleo, SuccessFactors, Ashby), and which "ATS score" claims we never make. Use when building or changing resume templates, the renderer, the ATS check, or any UI/marketing copy about ATS.
---

# ATS Compliance

## 1. What an ATS actually does (and doesn't)

Sources for everything here are in `docs/research/2026-10-market-research.md` §3.

- **Parses** the uploaded file into fields (contact, work history, education, skills) to fill the candidate profile and the application form. Bad layouts fail *here*: garbled order, a missing email, merged jobs. Greenhouse sends resumes it can't parse to manual review. Image-only PDFs and contact details in headers or footers are the most consistent failures.
- **Lets recruiters search and filter** by keywords, titles, location and knockout answers. Literal keyword presence in the parsed text matters.
- **Knockout or screening questions** (work authorization, location, years of experience, salary) are the main source of real automatic rejection. Greenhouse application rules and Ashby auto-reject both act on these answers. Resume wording doesn't change them.
- **How AI ranking actually grades (2025–26):**
  - Workday HiredScore grades A–D against the JD's *basic and preferred qualifications*, and added an LLM "Fit & Gap" view in Aug 2026.
  - Greenhouse Talent Matching puts candidates in five bands and doesn't auto-advance or auto-reject.
  - Ashby marks each criterion "meets / does not meet" with citations.

  **So: verifiable evidence for each basic qualification beats keyword density.** That's why the Match Report maps every must-have to evidence.
- **Myth:** "75% of resumes are rejected by ATS before a human sees them." It traces back to Preptel, a defunct company that never published a methodology. In vendor interviews, 92% of recruiters said their ATS doesn't auto-reject on the resume itself. **Never repeat the myth.** The honest framing: *a resume that parses cleanly and shows evidence for each requirement, in the job's own language, is easier to find, easier to grade and easier to read.*
- **Hidden prompt-injection text** in resumes (white text addressed to AI screeners) is common (41% of US job seekers admit it, per a Greenhouse survey) and increasingly caught (22% of hiring managers report it). We strip it from uploads and never generate it.

## 2. Template rules (Typst + DOCX; every template must pass all of them)

| Rule | Why |
|------|-----|
| Single column, top-to-bottom reading order | Two-column layouts interleave text in many parsers |
| Standard headings: Summary, Experience, Education, Skills, Projects, Certifications | Section detection keys off known names |
| Contact info in the body (top), **not** in the page header or footer | Several parsers skip headers and footers |
| No tables, text boxes, columns or shapes for content | They extract out of order or not at all |
| No icons or icon fonts (☎ ✉ Font Awesome) | They extract as private-use garbage. Write "Email:" or just the address |
| Visible URLs (`linkedin.com/in/name`), not hyperlinked words | Parsers keep the text, not the link target |
| **Ligatures off** (`#set text(ligatures: false)` in Typst) | `ﬁ`/`ﬂ` glyphs break keyword matching ("certiﬁed") |
| **Hyphenation off** (`#set text(hyphenate: false)`) | "Kuber-netes" split across lines breaks keyword matching |
| Dates inline under the title ("Mar 2022 – Present \| City"), never right-aligned with `h(1fr)` | pdfminer extracts a right-aligned date as a separate block, read after the whole entry |
| Fonts with coverage for the user's script (e.g. Noto Sans for Devanagari names) | A missing glyph renders as tofu and extracts as `(cid:N)`. The round-trip check blocks it |
| Open, embeddable fonts with good Unicode maps: Inter, Source Sans 3, IBM Plex Sans, Lato, Noto Sans (for Indic or non-Latin names) | Text extracts correctly, and there are no licensing issues |
| Body 10–11.5 pt, headings 12–14 pt, margins 0.5–0.8 in | Readability and the fit-to-page loop |
| Dates `Mon YYYY – Mon YYYY` everywhere | Date parsing and employment-gap calculation |
| Bullets as real characters (`•` U+2022 or `-`) | Image or custom bullets vanish |
| Page size **US Letter** for US/Canada, **A4** elsewhere | Recruiters notice, and printing breaks |
| PDF metadata: Title "{{FULL_NAME}} – Resume", Author {{FULL_NAME}}; tagged PDF where the Typst version supports it | Some systems show the title, and tagging helps accessibility |
| File size < 1 MB, file name `First-Last-Resume-Company.pdf` | Upload limits, and the recruiter's downloads folder |
| DOCX: real Word styles (Heading 1/2, List Bullet), no text boxes, no layout tables | Older parsers (e.g. Taleo-era) handle styled DOCX best |

Visual identity comes from typography, spacing and one accent color for headings. It never comes from layout tricks.

## 3. Deterministic round-trip check (`server/app/features/rendering/ats_roundtrip.py`)

Runs on **every** render, before the UI shows a "passed" badge:

1. Extract the text with `pdfminer.six` **and** `pypdf`, and normalize whitespace. The two extractors must agree on section order (fuzzy match ≥ 0.95).
2. Detect section headings in the expected order.
3. Email and phone regexes match within the first ~15% of the text (checked after placeholder restoration).
4. Every date token parses, and roles are in reverse-chronological order.
5. Keyword coverage: `JobSpec.keywords` (with synonyms, lemmatized, case-insensitive) counted **in the extracted text**, never in our JSON.
6. Must-have coverage: share of `must_have` items with ≥1 evidencing bullet *and* the term present in the text.
7. No private-use Unicode, no ligature glyphs, and no text smaller than 8 pt.

Output `AtsCheck { parse_ok, sections_found[], contact_found, date_issues[], keyword_coverage, must_have_coverage, issues[] }`. Any `parse_ok = false` blocks the download button and opens a "fix" suggestion.

Optional third opinion for template development: the open-source OpenResume parser (it shows how a generic parser reads a PDF). Run it in CI over the template fixtures, not in production.

## 4. Vendor notes (verify with round-trip fixtures; don't hardcode folklore)

| ATS | What to know |
|-----|--------------|
| Workday | It parses the resume to **autofill a long multi-page form**, and users must review each field. Clean single-column PDFs or DOCX autofill best. Usually detectable from `myworkdayjobs.com` URLs |
| Greenhouse | Accepts PDF/DOCX. Recruiters often read the resume itself. Custom application questions are common (our Outreach and "application answers" features help there) |
| Lever | Resume-first, and it parses into a candidate profile. PDF is fine |
| iCIMS | Widely used by large employers. PDF/DOCX. Some instances have AI matching enabled |
| SAP SuccessFactors / Oracle Taleo | Older parsers. DOCX with real styles tends to parse best, and plain formatting matters more here |
| Ashby | Modern, used by many startups. PDF is fine |

When `ats_vendor` is known, the UI can suggest the format (e.g. "Workday detected: we recommend uploading the DOCX and double-checking the autofilled fields").

## 5. Claims we never make (UI, marketing, emails)

- "Guaranteed to pass ATS" / "100% ATS-proof" / "beat the bots"
- A single universal "ATS score" presented as what employers see
- "Get hired / get interviews guaranteed"
- Repeating the 75% rejection myth

Allowed: "See exactly what an ATS reads from your resume", "Parses cleanly in our tests with two independent extractors", "Covers 11 of 12 must-have requirements from this job".
