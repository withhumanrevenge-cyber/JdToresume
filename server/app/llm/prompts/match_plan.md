## Task: analyse the fit between this candidate and the job in <job_spec>, and plan the tailoring

- requirement_matches: exactly one entry per requirement in job_spec.requirements, same order.
  - "evidenced": at least one fact clearly proves it.
  - "partial": related but weaker evidence (an adjacent tool, fewer years, coursework or a side project only).
  - "gap": nothing in the profile supports it.
  - evidence_fact_ids: only ids that exist in the profile. note: one short sentence explaining the status.
- fact_relevance: score every fact id in the profile: 3 = directly evidences a basic requirement, 2 = relevant, 1 = weak, 0 = irrelevant to this job.
- keyword_plan: job terms (exact job spelling) that the resume can use truthfully because the profile supports them. Exclude every gap.
- angle: one or two sentences on how to position this person for this job (which experience leads, what story the top third tells).
- gap_questions: at most 3 short questions about basic requirements marked "gap" or "partial" where the honest answer could plausibly be yes and would change the resume (for example "Have you used Kafka, even in a side project?"). Ask nothing the profile already answers.
