---
name: aws-standards
description: AWS architecture standards covering ECS, Aurora, S3, IAM Roles, Secrets Manager, presigned URLs, CloudWatch, and cost governance.
---

# AWS Infrastructure Standards

This skill provides operational and architectural standards for deploying and managing AWS-first production infrastructure.

## Core AWS Managed Services

- **Compute**: AWS ECS (Fargate) for containerized application services.
- **Database**: AWS Aurora PostgreSQL Serverless v2 for scalable relational data.
- **Caching & Queues**: ElastiCache for Redis, AWS SQS, AWS EventBridge.
- **Security & Storage**: AWS IAM Roles, AWS Secrets Manager, AWS S3.
- **Observability**: AWS CloudWatch (Logs, Metrics, Alarms).

---

## Security & Identity Rules

### 1. IAM Roles over Permanent Credentials
- Never hardcode AWS Access Keys (`AKIA...`) or Secret Keys in repository code, environment files, or Docker images.
- Use IAM Task Roles for ECS, IAM Execution Roles, and AWS IAM OIDC for CI/CD pipelines.

### 2. AWS Secrets Manager
- Retrieve database passwords, API keys, and third-party tokens dynamically from AWS Secrets Manager or Parameter Store at startup.
- Cache secret lookups locally in memory with TTL to avoid excess Secrets Manager API calls.

---

## S3 File Storage & Transfer Patterns

### 1. Presigned URLs for Uploads/Downloads
- Never stream or proxy binary user uploads through backend application servers unless transformation or strict middleware validation is required.
- Issue short-lived S3 presigned URLs (`generate_presigned_url`) for direct client-to-S3 uploads and downloads.

```python
# FastAPI Example: Presigned S3 Upload URL
@router.post("/uploads/presigned-url")
async def get_presigned_upload_url(filename: str, file_type: str):
    s3_client = boto3.client('s3')
    url = s3_client.generate_presigned_url(
        ClientMethod='put_object',
        Params={
            'Bucket': BUCKET_NAME,
            'Key': f"uploads/{uuid.uuid4()}/{filename}",
            'ContentType': file_type,
        },
        ExpiresIn=300
    )
    return {"upload_url": url}
```

### 2. S3 Multipart Uploads & Lifecycle Policies
- Enable multipart uploads for any file exceeding 5Mb.
- Configure lifecycle rules to transition old artifacts to Glacier or expire temporary upload chunks after 7 days.

---

## Scalability & Cost Governance

- **Horizontal Auto-scaling**: Configure ECS Fargate task auto-scaling based on CPU/Memory thresholds and target request count.
- **Aurora Serverless Scaling**: Define strict min/max ACU bounds to prevent runaway cost spikes.
- **Cost Monitoring**: Set up CloudWatch Cost Anomaly Detection alarms.

---

## Tailor: Lean MVP Profile (overrides the defaults above until the trigger is hit)

AWS spend is small next to LLM tokens and marketing. Don't pay for scale or availability we haven't earned yet, but keep the security rules above unchanged.

| Default above | MVP choice | Switch when |
|---------------|------------|-------------|
| Aurora PostgreSQL Serverless v2 | **RDS PostgreSQL `db.t4g.small`, single-AZ**, automated backups + PITR (7 days) | Paying users exist (→ Multi-AZ), or load gets spiky or connections run out (→ Aurora Serverless v2 + RDS Proxy) |
| Private subnets + NAT | **Public subnets, tasks with public IPs, security groups allowing ingress from the ALB only.** Gateway VPC endpoint for S3 (free) | A compliance or B2B customer requires private networking (NAT ≈ $33/mo + $0.045/GB per AZ) |
| x86 Fargate | **ARM64 (Graviton) Fargate**, about 20% cheaper. Worker and fetcher on **Fargate Spot** | Never: stay on ARM |
| ElastiCache cluster | **ElastiCache Serverless (Valkey)** | Steady high throughput makes a node cheaper |
| Always-on fetcher | **Fetcher scales 0→N on SQS depth** | Steady demand |

Product-specific rules:
- **Region:** a single region near the launch market (`ap-south-1` for India-first, `us-east-1` for US-first). Every bucket, DB and queue goes in that region.
- **PII buckets** (`uploads`, `renders`): SSE-KMS with a customer-managed key, Block Public Access on, bucket policy denying non-TLS access, and object keys `users/{user_id}/...`. Presigned URLs ≤ 5 min.
- **Lifecycle:** `renders/` expire after 30 days (they're re-creatable from JSON). Incomplete multipart uploads abort after 1 day. `uploads/` follow the user's retention setting.
- **Budgets:** AWS Budgets alerts at 50/80/100% of the monthly plan, plus Cost Anomaly Detection. LLM spend isn't on the AWS bill: alarm on it from the `llm_calls` ledger (a daily total and cost-per-pack p95).
- **LLM secrets:** the Groq API key lives in Secrets Manager, is read at startup through the task role and cached with a TTL, and never appears in task definitions or images. Use separate Groq projects or keys for prod (Zero Data Retention on) and evals (Batch allowed).
- **IaC:** Terraform modules under `infra/terraform/` (network, ecs-service, rds, s3, sqs, secrets). No console-created resources in prod.
