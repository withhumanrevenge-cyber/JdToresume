"use client"

import { useEffect, useId, useState } from "react"
import Link from "next/link"
import { CircleAlert, Sparkles } from "lucide-react"
import { cn } from "cn"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { usePlan } from "@/features/billing/api"
import { GenerationProgress } from "@/features/generate/components/generation-progress"
import type { Mode, RunError } from "@/features/generate/generation-runs"
import { useGenerationStream } from "@/features/generate/use-generation-stream"
import { useProfile } from "@/features/profile/api"
import type { Schemas } from "@/lib/api/client"
import { formatDate } from "@/lib/format"

type ModeOption = { mode: Mode; title: string; detail: string; available: boolean; note: string }

/** What each mode costs this user right now, so limits are visible before they press Generate, not after. */
function modeOptions(plan: Schemas["PlanOut"]): ModeOption[] {
  const left = Math.max(plan.packs.limit - plan.packs.used, 0)
  const paid = plan.plan !== "free"
  return [
    {
      mode: "deep",
      title: "Deep",
      detail: "Best quality: a stronger rewrite and a second fact check. About 20 seconds.",
      available: paid ? left > 0 : plan.deep_credits > 0,
      note: paid ? "Included in your plan" : plan.deep_credits > 0 ? `Uses 1 of your ${plan.deep_credits} Deep packs` : "Comes with a paid plan",
    },
    {
      mode: "quick",
      title: "Quick",
      detail: "Faster, with the same truthfulness checks. About 10 seconds.",
      available: left > 0,
      note: paid ? "Included in your plan" : `${left} of ${plan.packs.limit} free packs left this month`,
    },
  ]
}

export function GeneratePanel({ applicationId, hasPack }: { applicationId: string; hasPack: boolean }) {
  const plan = usePlan()
  const profile = useProfile()
  const generation = useGenerationStream(applicationId)
  const [chosen, setChosen] = useState<Mode | null>(null)
  const legendId = useId()

  if (plan.isPending || profile.isPending) {
    return <Skeleton className="h-56 w-full rounded-xl" />
  }

  const options = plan.data ? modeOptions(plan.data) : []
  const fallback = options.find((option) => option.mode === plan.data?.next_pack_mode && option.available)?.mode ?? null
  const selected = chosen && options.find((option) => option.mode === chosen)?.available ? chosen : fallback
  const noProfile = profile.data === null
  const nothingLeft = plan.data?.next_pack_mode === null
  const showProgress = generation.status !== "idle" && (generation.runId !== null || generation.status === "starting")

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg font-semibold">
          <Sparkles className="size-5 text-primary" aria-hidden />
          {hasPack ? "Generate a new version" : "Generate your application pack"}
        </CardTitle>
        <CardDescription>
          A tailored resume, cover letter and outreach messages. Every line comes from your profile.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-5">
        {noProfile ? (
          <Alert variant="warning">
            <CircleAlert aria-hidden />
            <AlertTitle>Upload your resume first</AlertTitle>
            <AlertDescription>
              The pack is written from your profile. <Link href="/profile">Upload your resume</Link>, then come back.
            </AlertDescription>
          </Alert>
        ) : nothingLeft && plan.data ? (
          <NothingLeft plan={plan.data} />
        ) : (
          <fieldset className="flex flex-col gap-3" disabled={generation.active}>
            <legend id={legendId} className="mb-1 text-sm font-medium">Quality</legend>
            <RadioGroup
              aria-labelledby={legendId}
              value={selected ?? ""}
              onValueChange={(value) => setChosen(value as Mode)}
              className="grid gap-3 sm:grid-cols-2"
            >
              {options.map((option) => (
                <Label
                  key={option.mode}
                  htmlFor={`mode-${option.mode}`}
                  className={cn(
                    "flex cursor-pointer items-start gap-3 rounded-xl border p-4 font-normal transition-colors",
                    "has-[[data-state=checked]]:border-primary has-[[data-state=checked]]:bg-secondary",
                    !option.available && "cursor-not-allowed opacity-60",
                  )}
                >
                  <RadioGroupItem id={`mode-${option.mode}`} value={option.mode} disabled={!option.available} className="mt-0.5" />
                  <span className="flex flex-col gap-1">
                    <span className="font-medium">{option.title}</span>
                    <span className="text-sm text-muted-foreground">{option.detail}</span>
                    <span className="text-xs font-medium text-muted-foreground">{option.note}</span>
                  </span>
                </Label>
              ))}
            </RadioGroup>
          </fieldset>
        )}

        <div className="flex flex-wrap items-center gap-3">
          <Button
            size="lg"
            disabled={generation.active || noProfile || nothingLeft || !selected}
            onClick={() => generation.start(selected ?? undefined)}
          >
            {generation.active ? <Spinner /> : <Sparkles aria-hidden />}
            {generation.active ? "Writing your pack…" : hasPack ? "Generate again" : "Generate pack"}
          </Button>
          {generation.active && generation.startedAt && <Elapsed since={generation.startedAt} />}
        </div>
        {!noProfile && !nothingLeft && (
          // The billing rule, stated before anyone pays (server/app/features/billing/service.py).
          <p className="text-sm text-muted-foreground">If the resume can&apos;t be written, the pack isn&apos;t counted.</p>
        )}

        {showProgress && <GenerationProgress state={generation} />}
        {generation.status === "failed" && generation.error && <RunFailed error={generation.error} />}
      </CardContent>
    </Card>
  )
}

function NothingLeft({ plan }: { plan: Schemas["PlanOut"] }) {
  const resets = plan.packs.resets_at ? formatDate(plan.packs.resets_at) : null
  return (
    <Alert variant="warning">
      <CircleAlert aria-hidden />
      <AlertTitle>{plan.plan === "free" ? "You've used this month's free packs" : "You've reached this week's fair-use limit"}</AlertTitle>
      <AlertDescription>
        {resets ? `More packs from ${resets}. ` : ""}
        <Link href="/account">See your plan</Link>
      </AlertDescription>
    </Alert>
  )
}

/** A refused or broken run, with what to do next. */
function RunFailed({ error }: { error: RunError }) {
  const resetsAt = typeof error.details?.resets_at === "string" ? formatDate(error.details.resets_at) : null
  const action =
    error.code === "profile_required" ? <Link href="/profile">Upload your resume</Link>
    : error.code === "quota_exceeded" || error.code === "upgrade_required" ? <Link href="/account">See your plan</Link>
    : null
  return (
    <Alert variant="destructive" role="alert">
      <CircleAlert aria-hidden />
      <AlertTitle>{error.code === "upstream_error" ? "Part of the pack wasn't written" : "The pack wasn't generated"}</AlertTitle>
      <AlertDescription>
        {error.message}
        {resetsAt && ` Your free packs come back on ${resetsAt}.`} {action}
      </AlertDescription>
    </Alert>
  )
}

function Elapsed({ since }: { since: number }) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [])
  return <span className="text-sm text-muted-foreground tabular-nums">{Math.max(0, Math.round((now - since) / 1000))} s</span>
}
