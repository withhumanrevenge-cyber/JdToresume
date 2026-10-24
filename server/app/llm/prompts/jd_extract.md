## Task: extract a JobSpec from the posting in <job_description>

The posting may be pasted from a web page or a screenshot and may contain navigation text, "Apply now" buttons, benefits and legal boilerplate. Extract what a candidate needs to tailor an application.

- requirements: every distinct qualification, in order of appearance, with ids r1, r2, …
  - tier "basic" for required, must-have or minimum qualifications; tier "preferred" for nice-to-have, bonus, "a plus" or "familiarity with". When the posting does not label them, judge from wording: "must", "required", "X+ years", "you have" → basic; "ideally", "bonus", "plus", "exposure to", "nice to have" → preferred.
  - Split compound requirements when each part could be evidenced separately ("Go and Kafka" → two). Keep genuine alternatives together in one requirement and list every option in evidence_terms ("Go or Java").
  - evidence_terms: the posting's exact spelling first, then common variants (e.g. "Kubernetes", "K8s").
- responsibilities: the main duties, trimmed, at most 10.
- keywords: skills, tools, methods and domain terms a recruiter would search for. Exact posting spelling in `term`; weight 3 = central to the role, 2 = important, 1 = mentioned once.
- company_signals: concrete facts about the company or team (product, customers, scale, stack, a problem they name) that could open a cover letter. Skip generic claims such as "fast-paced" or "innovative".
- Ignore EEO statements and benefits, except for location, remote policy, visa sponsorship and salary.
- unreadable_fields: list anything you could not determine. Never guess company, salary or sponsorship; use null or "unknown".
