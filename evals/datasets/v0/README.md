# Eval dataset v0

12 hand-written cases for the tailoring pipeline. Each file in `cases/` is one `EvalCase` (see `evals/case.py`): a `CareerProfile`, `ContactDetails`, the job description text a user would paste, and `expectations`.

> **Synthetic data.** Every person, employer, school, award and job posting here is fictional. Contact details are deliberately fake (`@example.com` emails, `+1 555-01xx` / `+91 90000 0xxxx` / `+44 7700 900xxx` phone numbers, `linkedin.com/in/example-…` links). Real product and certification names (AWS, Salesforce, CCRN, GA4 and so on) appear only as skills, tools and credentials. Any resemblance to real people or companies is unintended.

Load them with:

```
./.venv/Scripts/python.exe -c "from evals.case import load_cases; cs=load_cases('v0'); print(len(cs), [c.id for c in cs])"
```

## Cases

| id | Persona | Region | Trap terms (claiming = fabrication) | Other traps (`trap_notes`) |
|----|---------|--------|-------------------------------------|----------------------------|
| `in-fresher-swe` | B.Tech CSE fresher (Java/Spring Boot projects, 1 internship, CGPA) → SDE-1 backend at a Bengaluru product company | IN · en-IN · 1 page | Go, Kubernetes | Intern title upgrade, stretching "Docker basics", presenting a laptop load test as production traffic |
| `in-fresher-data-analyst` | Tier-2 B.Com grad with SQL/Excel/Power BI coursework projects → junior data analyst (**messy job-board paste**) | IN · en-IN · 1 page | Tableau, Python, pandas | Power BI→Tableau swap, coursework presented as client work, retitling the MIS internship |
| `us-newgrad-intl-swe` | MS CS on F-1 OPT, 2 yrs at an Indian IT firm + 1 US internship → new-grad cloud SWE (JD states H-1B sponsorship) | US · en-US · 1 page | AWS Certified Developer – Associate | Inflating class-project AWS use, SAM→CDK, "no sponsorship required" |
| `us-backend-mid` | 5 yrs Java/Spring at a logistics company (RabbitMQ, freight billing) → payments platform | US · en-US · 1 page | Go, Golang, Kafka | RabbitMQ→Kafka, billing passed off as payments/PCI, mentoring presented as leading |
| `us-pm-switcher` | Operations analyst → Associate PM (returns product) | US · en-US · 1 page | Amplitude, A/B testing | "Supported 3 launches" → "led", team result claimed solo, title change |
| `us-nurse-icu` | RN, 3 yrs med-surg/tele (BLS, ACLS) → MICU nights | US · en-US · 1 page | CCRN | Step-down floating presented as ICU experience, relief charge → Charge Nurse |
| `in-sales-bdr` | Inside-sales rep at Indian B2B SaaS (HubSpot, Apollo, BANT) → enterprise BDR | IN · en-IN · 1 page | Salesforce, ZoomInfo | SMB sold as enterprise, pipeline called revenue, BANT→MEDDICC |
| `uk-marketing-manager` | 7 yrs marketing, owns £250k paid social, manages 2 → Senior Marketing Manager (CV) | UK · en-GB · 2 pages | GA4 certification, Marketo | £250k → £1M+, team size, shortlist called a win |
| `us-devops-senior` | 10 yrs, Terraform + AWS ECS/Fargate → platform role on EKS | US · en-US · 2 pages | Kubernetes, EKS, CKA | ECS→EKS, mentoring presented as managing, keeping the cert the candidate really holds |
| `us-data-scientist-laidoff` | Laid off from adtech (Python, sklearn, XGBoost) → healthcare ML engineer | US · en-US · 1 page | PyTorch, HIPAA, EHR, PHI | CCPA→HIPAA, Keras prototype→PyTorch, hiding the layoff end date |
| `in-frontend-mid` | 3 yrs React/JS in Pune (TS + Next.js in one side project) → fintech SDE-2 web | IN · en-IN · 1 page | React Native | "Strong TypeScript", production Next.js, coverage rounded up to 80% |
| `us-ux-designer` | 4 yrs product designer, mentored 2 interns → design lead (**prose JD, no labelled sections**) | US · en-US · 1 page | ProtoPie, People management | Mentoring interns → "managed a team of designers", Principle→ProtoPie, title upgrade |

## Conventions

- **`evidenced_terms`** (4–8 per case) are spelled exactly as in the JD and are genuinely supported by at least one profile fact or skill. A good tailored resume should contain them.
- **`trap_terms`** (1–4 per case) are spelled exactly as in the JD. None of them appears anywhere in the case's profile, which was checked with a case-insensitive whole-word match. Any output containing one is a fabrication.
- **`trap_notes`** cover temptations that aren't single terms: title inflation, number or scope inflation, tool swaps, and domain claims.
- Fact ids are unique within each profile (`f-<employer>-<n>`). Every skill's `evidence_fact_ids` points at real facts, and a few skills have empty evidence (declared by the user). `style.voice_samples` are verbatim fact texts.
- JDs are 300–450 words and vary in format on purpose: different bullet characters, numbered lists, "Requirements / Nice to have" splits under different labels, EEO and benefits boilerplate. One is a messy job-board paste (`in-fresher-data-analyst`) and one is all prose (`us-ux-designer`).
