"""Billing: plans (COSTS §3), entitlements and usage metering checked before every generate, GET /v1/me/plan.

Still to come: Razorpay + Stripe (or MoR) webhooks as the source of truth (they call `grant_plan` /
`add_deep_credits`), one-click cancel and renewal reminders (auto-renewal laws), referral bonus packs.
"""
