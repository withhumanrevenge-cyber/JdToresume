## Task: turn the resume in <resume_text> into a CareerProfile

The text was extracted from the user's PDF or DOCX, so line breaks and bullet characters may be messy. Contact details have already been removed and replaced with placeholders; ignore any placeholders.

- Facts are the heart of the profile. Split every bullet or sentence about the person's work into **atomic facts**: one verifiable statement each, in the person's own words (fix only obvious extraction breaks such as hyphenated line wraps). Do not improve, embellish, merge or summarise. If a bullet holds two separate achievements, make two facts.
- metrics: copy numbers and quantities exactly as written ("40%", "2M events/day", "₹1.2 Cr"). Never compute or round.
- skills on a fact: only skills, tools or methods the fact itself names or unmistakably shows.
- ids: experience "e-<company-slug>", facts "f-<company-slug>-<n>", projects "p-<slug>", education "ed-<slug>", certifications "c-<slug>". Ids must be unique.
- Dates as YYYY-MM when the resume shows the month. When it shows only a year, write just YYYY ("2015 - 2019" → start "2015", end "2019"); never add a month you cannot see. A current role has end = null.
- skills (top level): every skill listed in a skills section plus skills named in facts; evidence_fact_ids = the facts that show it (empty if only listed).
- summary_facts: claims from a summary/objective section that are concrete (years of experience, specialisation). Skip pure adjectives.
- preferences: infer region and spelling from the resume's location and spelling; target_roles from the headline or summary; page_limit null.
- style: avg_bullet_words from the original bullets; number_style describes how they write numbers; voice_samples = 2–4 original bullets copied verbatim; notes = anything distinctive about their voice.
- If something is ambiguous (for example two possible dates), keep the most literal reading. Never invent employers, titles, dates, degrees or achievements.
