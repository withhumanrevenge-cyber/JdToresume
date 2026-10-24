## Task: audit the resume in <tailored_resume> against the candidate's profile, like a sceptical hiring manager preparing interview questions

For the summary and every bullet, check each claim against the facts it cites (source_fact_ids) and the rest of the profile. Report:
- unsupported_claim: a claim that the cited facts do not contain.
- inflated_number: a number that is missing from, or larger than, the facts.
- inflated_scope: more ownership, seniority, scope or team size than the facts show ("led" when the fact says "helped", "architected" when it says "contributed").
- title_change: any implied title or seniority the profile does not hold.
- new_skill: a skill, tool or certification the profile does not support (also check skill_groups).
- banned_phrase or generic: a banned phrase, or a bullet so generic it could belong to anyone.

Quote the exact text. Severity "high" = would embarrass the candidate if asked about it in an interview; "medium" = misleading emphasis; "low" = style only.
If the resume is clean, return an empty list. Do not invent violations to look thorough.
