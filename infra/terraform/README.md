# infra/terraform

```
modules/
  network/       VPC, public subnets + security groups (no NAT at MVP), S3 gateway endpoint
  ecs-service/   one Fargate ARM service (API, worker on Spot, fetcher 0->N) + autoscaling
  rds/           PostgreSQL (t4g.small single-AZ -> Multi-AZ at launch), PITR backups
  s3/            uploads + renders buckets: SSE-KMS, block public access, lifecycle rules
  sqs/           queues + DLQs (render, parse, email, fetch)
  secrets/       Secrets Manager entries (Groq key, DB, payment providers) + KMS keys
envs/
  staging/       smaller copy of prod, synthetic users
  prod/          single region near the launch market (ap-south-1 or us-east-1)
```
State in S3 with locking; CI applies staging automatically and prod after manual approval.
