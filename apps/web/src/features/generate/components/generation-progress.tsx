"use client"

import { CircleCheck, CircleDashed, CircleX } from "lucide-react"
import { cn } from "cn"

import { Spinner } from "@/components/ui/spinner"
import type { GenerationState, PieceKind } from "@/features/generate/generation-runs"

const STEPS: { kind: PieceKind; label: string; ready: string }[] = [
  { kind: "match_report", label: "Matching your experience to the job", ready: "Match report ready" },
  { kind: "resume", label: "Tailoring and fact-checking your resume", ready: "Resume ready" },
  { kind: "cover_letter", label: "Writing the cover letter", ready: "Cover letter ready" },
  { kind: "outreach", label: "Drafting outreach messages", ready: "Outreach messages ready" },
]

type StepStatus = "waiting" | "working" | "done" | "failed"

function stepStatus(kind: PieceKind, state: GenerationState): StepStatus {
  if (state.pieces[kind]) return "done"
  if (state.status === "failed") return "failed"
  if (state.status === "done") return "done"
  const matched = Boolean(state.pieces.match_report)
  if (kind === "match_report" || matched) return "working" // the other three run in parallel once matching is done
  return "waiting"
}

/** Each step as it happens (never one long spinner), announced to screen readers as pieces arrive. */
export function GenerationProgress({ state }: { state: GenerationState }) {
  const announcement = announcementFor(state)
  return (
    <div className="rounded-xl border bg-background p-4">
      <ol className="flex flex-col gap-3" aria-label="Progress">
        {STEPS.map((step) => {
          const status = stepStatus(step.kind, state)
          return (
            <li key={step.kind} className="flex items-center gap-3 text-sm">
              <StepIcon status={status} />
              <span className={cn(status === "waiting" && "text-muted-foreground", status === "done" && "font-medium")}>
                {step.label}
              </span>
              <span className="sr-only">
                {status === "done" ? "(done)" : status === "working" ? "(in progress)" : status === "failed" ? "(not finished)" : "(waiting)"}
              </span>
            </li>
          )
        })}
      </ol>
      <p className="sr-only" aria-live="polite">{announcement}</p>
    </div>
  )
}

function StepIcon({ status }: { status: StepStatus }) {
  if (status === "done") return <CircleCheck className="size-5 shrink-0 text-success" aria-hidden />
  if (status === "failed") return <CircleX className="size-5 shrink-0 text-destructive" aria-hidden />
  if (status === "working") return <Spinner className="size-5 shrink-0 text-primary" />
  return <CircleDashed className="size-5 shrink-0 text-muted-foreground" aria-hidden />
}

/** "Resume ready", then "Cover letter ready"…: the live region repeats whichever piece arrived last. */
function announcementFor(state: GenerationState): string {
  if (state.status === "done") return "Your pack is ready"
  return STEPS.find((step) => step.kind === state.lastPiece)?.ready ?? ""
}
