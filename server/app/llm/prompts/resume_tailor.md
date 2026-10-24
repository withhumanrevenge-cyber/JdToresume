## Task: write the tailored resume for the job in <job_spec>, using the plan in <match_report>

Structure
- section_order by career stage. Students and freshers: summary, education, projects, experience, skills, certifications. Experienced candidates: summary, experience, skills, projects (only if they add evidence), education, certifications. Career switchers lead with whichever section holds the strongest evidence for the target role.
- experience: reference roles by experience_id, newest first. Do not write titles, companies or dates; they are taken from the profile. Give recent or relevant roles 3–6 bullets and older or less relevant roles 1–3. Order bullets inside a role by how directly they evidence basic requirements.
- projects and education: reference ids. Education bullets only for relevant facts (coursework, grade, award) that exist in the profile.
- Fit preferences.page_limit: one page holds roughly 450–550 words of content, two pages roughly 800–1000. Drop low-relevance facts (see fact_relevance) rather than shrinking every bullet.

Bullets
- Action, then what, then how or with which tools, then the result. Include a number only if it appears in a cited fact.
- About 14–28 words. Past tense for past roles, present tense for a current role. No pronouns. Within a role, start each bullet with a different verb; plain verbs (built, cut, shipped, ran, wrote, fixed, migrated, sold) beat inflated ones.
- Use the exact job terms from match_report.keyword_plan where they are true. Each important evidenced term should appear in the skills section and in at least one bullet.
- source_fact_ids: every fact the bullet relies on. targets_requirement_ids: the requirement ids it evidences.

Summary
- Two or three lines: the target role's language, years or stage, core specialty, one or two proof points. No "I". Cite summary_source_fact_ids.

Skills
- skill_groups: 3–5 groups (for example Languages, Frameworks, Cloud & Infra, Data, Tools), at most 25 skills in total, only skills the profile supports, using the job's spelling when it names the same thing.
- certification_ids: only relevant certifications that exist in the profile.

Never include anything the match report marks as a gap.
