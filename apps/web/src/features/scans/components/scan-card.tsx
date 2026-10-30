"use client"

import Link from "next/link"
import { CircleAlert, RefreshCw, ScanSearch } from "lucide-react"

import { QueryError } from "@/components/query-error"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { MatchReport } from "@/features/pack/components/match-report"
import { useLatestScan, useRunScan } from "@/features/scans/api"
import { ApiError, errorMessage, type Schemas } from "@/lib/api/client"
import { formatPercent } from "@/lib/format"

/**
 * The free match scan (PRD §4): how the current profile lines up with this job, before spending a pack. Shown on an
 * application that has no pack yet; once a pack exists, its own match report takes over.
 */
export function ScanCard({ jobId, job }: { jobId: string; job: Schemas["JobSpec"] | undefined }) {
  const latest = useLatestScan(jobId)
  const run = useRunScan(jobId)
  const scan = latest.data

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg font-semibold">
          <ScanSearch className="size-5 text-primary" aria-hidden />
          Check your fit first
          <Badge variant="secondary">Free</Badge>
        </CardTitle>
        <CardDescription>
          See which requirements your resume already shows and which keywords are missing. It doesn&apos;t use a pack.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-5">
        {latest.isPending ? (
          <Skeleton className="h-10 w-40" />
        ) : latest.isError ? (
          <QueryError error={latest.error} onRetry={() => latest.refetch()} />
        ) : (
          <div className="flex flex-wrap items-center gap-3">
            <Button variant={scan ? "outline" : "default"} disabled={run.isPending} onClick={() => run.mutate()}>
              {run.isPending ? <Spinner /> : scan ? <RefreshCw aria-hidden /> : <ScanSearch aria-hidden />}
              {run.isPending ? "Scanning…" : scan ? "Scan again" : "Check my fit"}
            </Button>
            <p role="status" className="text-sm text-muted-foreground">
              {run.isPending
                ? "Comparing your profile with the job. This takes a few seconds."
                : scan
                  ? `${scan.scans_left_today} free scans left today`
                  : ""}
            </p>
          </div>
        )}

        {run.isError && <ScanFailed error={run.error} />}

        {scan && (
          <div className="flex flex-col gap-6">
            {scan.stale && (
              <Alert variant="warning">
                <CircleAlert aria-hidden />
                <AlertTitle>Your profile changed since this scan</AlertTitle>
                <AlertDescription>Scan again to see the match with your latest profile.</AlertDescription>
              </Alert>
            )}
            <KeywordSummary scan={scan} />
            <MatchReport report={scan.match_report} job={job} />
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function KeywordSummary({ scan }: { scan: Schemas["ScanOut"] }) {
  const total = scan.keywords_found.length + scan.keywords_missing.length
  if (total === 0) return null
  return (
    <section className="flex flex-col gap-3">
      <p>
        <span className="font-semibold tabular-nums">{scan.keywords_found.length} of {total}</span> job keywords are
        already in your profile
        {scan.keyword_coverage !== null && <span className="text-muted-foreground"> ({formatPercent(scan.keyword_coverage)})</span>}.
      </p>
      {scan.keywords_missing.length > 0 && (
        <div className="flex flex-col gap-2">
          <p className="text-sm text-muted-foreground">
            Not in your profile yet. Add them to your resume only if they&apos;re true for you:
          </p>
          <ul className="flex flex-wrap gap-2">
            {scan.keywords_missing.map((keyword) => (
              <li key={keyword}><Badge variant="outline" className="h-7 px-3 text-sm">{keyword}</Badge></li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

function ScanFailed({ error }: { error: unknown }) {
  const needsProfile = error instanceof ApiError && error.code === "profile_required"
  return (
    <Alert variant="destructive" role="alert">
      <CircleAlert aria-hidden />
      <AlertTitle>The scan didn&apos;t run</AlertTitle>
      <AlertDescription>
        {errorMessage(error)} {needsProfile && <Link href="/profile">Upload your resume</Link>}
      </AlertDescription>
    </Alert>
  )
}
