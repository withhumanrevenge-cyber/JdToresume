import { CircleAlert, CircleCheck } from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import type { Schemas } from "@/lib/api/client"
import { formatPercent } from "@/lib/format"

/**
 * The measured result of reading the file back like a parser would (ats-compliance). We show what was measured
 * (parse checks, keyword and must-have coverage), never a made-up "ATS score" (CLAUDE.md non-negotiable #3).
 */
export function AtsSummary({ view }: { view: Schemas["AtsView"] }) {
  const { check } = view
  return (
    <div className="flex flex-col gap-4">
      {check.parse_ok ? (
        <Alert className="border-transparent bg-success-muted text-success-muted-foreground">
          <CircleCheck aria-hidden />
          <AlertTitle>Reads cleanly as plain text</AlertTitle>
          <AlertDescription className="text-success-muted-foreground">
            Two independent parsers read the same words in the same order, found every section and your contact details.
          </AlertDescription>
        </Alert>
      ) : (
        <Alert variant="warning">
          <CircleAlert aria-hidden />
          <AlertTitle>{check.issues.length === 1 ? "1 thing a parser may trip on" : `${check.issues.length} things a parser may trip on`}</AlertTitle>
          <AlertDescription>
            <ul className="mt-1 list-disc pl-5">
              {check.issues.map((issue) => <li key={issue}>{issue}</li>)}
            </ul>
          </AlertDescription>
        </Alert>
      )}

      <dl className="grid gap-3 sm:grid-cols-3">
        <Measure label="Job keywords found" value={check.keyword_coverage === null ? "—" : formatPercent(check.keyword_coverage)} />
        <Measure label="Must-haves with evidence" value={check.must_have_coverage === null ? "—" : formatPercent(check.must_have_coverage)} />
        <Measure label="Pages" value={view.pages === null ? "Word decides" : String(view.pages)} />
      </dl>

      {check.keywords_missing.length > 0 && (
        <div className="flex flex-col gap-2">
          <p className="text-sm text-muted-foreground">
            Keywords from the posting that aren&apos;t in the text (added only where your experience backs them):
          </p>
          <ul className="flex flex-wrap gap-2">
            {check.keywords_missing.map((keyword) => (
              <li key={keyword}><Badge variant="outline" className="h-7 px-3 text-sm">{keyword}</Badge></li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function Measure({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border p-4">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="text-2xl font-semibold tabular-nums">{value}</dd>
    </div>
  )
}

/** The extracted plain text, exactly as a parser reads it: "What the ATS sees". */
export function AtsText({ view }: { view: Schemas["AtsView"] }) {
  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm text-muted-foreground">
        Sections found, in order: {view.check.sections_found.length ? view.check.sections_found.join(", ") : "none"}.
      </p>
      <pre
        tabIndex={0}
        aria-label="Text extracted from your resume"
        className="max-h-[36rem] overflow-auto rounded-xl border bg-muted p-4 font-mono text-sm leading-relaxed whitespace-pre-wrap [overflow-wrap:anywhere] focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
      >
        {view.text}
      </pre>
    </div>
  )
}
