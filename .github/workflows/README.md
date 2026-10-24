# .github/workflows

| Workflow | When | What it does |
|----------|------|--------------|
| `ci.yml` | Every pull request, every push to `main` | Four jobs, all **required** to merge into `main`: **backend** (ruff, migrations apply and match the models, all pytest suites against a real Postgres), **web** (typecheck, lint, unit tests, production build), **api-contract** (regenerates `packages/api-types` from the API and fails if the committed copy is stale), **api-image** (builds the API Docker image, checks it refuses dev sign-in in production, serves `/health` and renders a PDF) |
| `cd.yml` | Push to `main`, tags `v*` | Builds and pushes the API image to `ghcr.io/<owner>/jdtoresume-api` (`sha-<commit>`, `latest`, and the version on tags), with provenance and an SBOM |
| `evals.yml` | Pull requests touching `server/app/llm/`, `evals/` or the pipeline | Cost estimate always; live smoke eval with hard gates (fabrication 0, ATS parse 100%) when the `GROQ_API_KEY` secret is set |

Repository secrets and settings these use:
- `GITHUB_TOKEN` (automatic): CD pushes images with it (`packages: write`).
- `GROQ_API_KEY` (optional, add under Settings → Secrets and variables → Actions): turns on the live eval. Use a
  Developer-tier key with a spend limit; the free tier's rate limits make runs fail.

Not built yet (docs/engineering/WORK_LEFT.md, "Deploy"): AWS deploys (ECR, `terraform plan/apply`, ECS, staging
automatic and prod behind a manual approval) through GitHub OIDC, and connecting `apps/web` to Vercel.
