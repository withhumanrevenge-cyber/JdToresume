import { useQuery } from "@tanstack/react-query"

import { api, unwrap, type Schemas } from "@/lib/api/client"
import { formatDate } from "@/lib/format"

export const planKey = ["plan"] as const

export function usePlan() {
  return useQuery({ queryKey: planKey, queryFn: () => unwrap(api.GET("/v1/me/plan")) })
}

/** One short line about what's left, e.g. "2 of 3 free packs left" or "Sprint pass until 28 Oct 2026". */
export function allowanceSummary(plan: Schemas["PlanOut"]): string {
  const left = Math.max(plan.packs.limit - plan.packs.used, 0)
  if (plan.plan === "free") {
    const deep = plan.deep_credits > 0 ? ` · ${plan.deep_credits} Deep` : ""
    return `${left} of ${plan.packs.limit} free packs left${deep}`
  }
  return plan.expires_at ? `${plan.name} until ${formatDate(plan.expires_at)}` : plan.name
}
