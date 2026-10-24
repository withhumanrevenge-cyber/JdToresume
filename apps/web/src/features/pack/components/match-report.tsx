import { CircleCheck, CircleDot, CircleHelp, CircleMinus } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import type { Schemas } from "@/lib/api/client"

type Match = Schemas["RequirementMatch"]

const STATUS: Record<Match["status"], { label: string; icon: typeof CircleCheck; tone: string }> = {
  evidenced: { label: "Shown", icon: CircleCheck, tone: "text-success" },
  partial: { label: "Partly shown", icon: CircleDot, tone: "text-warning-muted-foreground" },
  gap: { label: "Gap", icon: CircleMinus, tone: "text-muted-foreground" },
}

/**
 * How the profile lines up with each requirement, must-haves first, the way employer-side screening grades it.
 * Status is always written out next to its icon, so colour is never the only signal.
 */
export function MatchReport({ report, job }: { report: Schemas["MatchReport"]; job: Schemas["JobSpec"] | undefined }) {
  const requirements = new Map((job?.requirements ?? []).map((requirement) => [requirement.id, requirement]))
  const tiered = (tier: "basic" | "preferred") =>
    report.requirement_matches.filter((match) => (requirements.get(match.requirement_id)?.tier ?? "basic") === tier)
  const basic = tiered("basic")
  const preferred = tiered("preferred")
  const shown = basic.filter((match) => match.status === "evidenced").length

  return (
    <div className="flex flex-col gap-8">
      <div className="grid gap-4 sm:grid-cols-3">
        <Stat value={`${shown} of ${basic.length}`} label="must-haves shown" />
        <Stat value={String(basic.filter((match) => match.status === "partial").length)} label="partly shown" />
        <Stat value={String(report.requirement_matches.filter((match) => match.status === "gap").length)} label="gaps, never invented" />
      </div>

      {report.angle && (
        <section className="rounded-xl bg-secondary p-4 text-secondary-foreground">
          <h3 className="mb-1 text-sm font-semibold">How you&apos;re positioned</h3>
          <p className="leading-relaxed">{report.angle}</p>
        </section>
      )}

      <RequirementList title="Must-haves" matches={basic} requirements={requirements} />
      {preferred.length > 0 && <RequirementList title="Nice to have" matches={preferred} requirements={requirements} />}

      {report.keyword_plan.length > 0 && (
        <section className="flex flex-col gap-3">
          <h3 className="text-sm font-semibold">Keywords used, spelled as in the posting</h3>
          <ul className="flex flex-wrap gap-2">
            {report.keyword_plan.map((keyword) => (
              <li key={keyword}><Badge variant="secondary" className="h-7 px-3 text-sm">{keyword}</Badge></li>
            ))}
          </ul>
        </section>
      )}

      {report.gap_questions.length > 0 && (
        <section className="flex flex-col gap-3">
          <h3 className="text-sm font-semibold">Questions that could close a gap</h3>
          <p className="text-sm text-muted-foreground">
            If any of these are true, add them to your resume and upload it again. Tailor won&apos;t claim them for you.
          </p>
          <ul className="flex flex-col gap-2">
            {report.gap_questions.map((question) => (
              <li key={question.requirement_id + question.question} className="flex items-start gap-2">
                <CircleHelp className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
                <span>{question.question}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div className="rounded-xl border p-4">
      <p className="text-2xl font-semibold tabular-nums">{value}</p>
      <p className="text-sm text-muted-foreground">{label}</p>
    </div>
  )
}

function RequirementList({ title, matches, requirements }: { title: string; matches: Match[]; requirements: Map<string, Schemas["Requirement"]> }) {
  if (matches.length === 0) return null
  return (
    <section className="flex flex-col gap-3">
      <h3 className="text-sm font-semibold">{title}</h3>
      <ul className="flex flex-col divide-y rounded-xl border">
        {matches.map((match) => {
          const status = STATUS[match.status]
          const Icon = status.icon
          return (
            <li key={match.requirement_id} className="flex items-start gap-3 p-4">
              <Icon className={`mt-0.5 size-5 shrink-0 ${status.tone}`} aria-hidden />
              <div className="flex min-w-0 flex-1 flex-col gap-1">
                <p className="leading-snug">{requirements.get(match.requirement_id)?.text ?? match.requirement_id}</p>
                {match.note && <p className="text-sm text-muted-foreground">{match.note}</p>}
              </div>
              <span className="shrink-0 text-xs font-medium text-muted-foreground">{status.label}</span>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
