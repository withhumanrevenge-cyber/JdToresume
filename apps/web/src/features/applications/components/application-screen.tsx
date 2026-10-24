"use client"

import { useState, type ReactNode } from "react"
import Link from "next/link"
import { ChevronLeft, ExternalLink } from "lucide-react"

import { PageHeader } from "@/components/page-header"
import { QueryError } from "@/components/query-error"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useApplication, useJob } from "@/features/applications/api"
import { RunStatusBadge } from "@/features/applications/components/run-status-badge"
import { GeneratePanel } from "@/features/generate/components/generate-panel"
import type { PieceKind, Pieces } from "@/features/generate/generation-runs"
import { useGenerationStream } from "@/features/generate/use-generation-stream"
import { CoverLetterPanel } from "@/features/pack/components/cover-letter-panel"
import { MatchReport } from "@/features/pack/components/match-report"
import { OutreachPanel } from "@/features/pack/components/outreach-panel"
import { ResumePanel } from "@/features/pack/components/resume-panel"
import type { Schemas } from "@/lib/api/client"
import { formatDate } from "@/lib/format"

const TABS: { kind: PieceKind; label: string }[] = [
  { kind: "match_report", label: "Match" },
  { kind: "resume", label: "Resume" },
  { kind: "cover_letter", label: "Cover letter" },
  { kind: "outreach", label: "Outreach" },
]

/** The saved pack, without the nulls the API uses for pieces that aren't there. */
function savedPieces(pieces: Schemas["Pieces"] | undefined): Pieces {
  return Object.fromEntries(Object.entries(pieces ?? {}).filter(([, value]) => value)) as Pieces
}

export function ApplicationScreen({ id }: { id: string }) {
  const application = useApplication(id)
  const job = useJob(application.data?.job.id)
  const generation = useGenerationStream(id)
  const [tab, setTab] = useState<PieceKind | null>(null)

  if (application.isPending) {
    return (
      <div className="flex flex-col gap-6">
        <Skeleton className="h-12 w-2/3" />
        <Skeleton className="h-56 w-full rounded-xl" />
      </div>
    )
  }
  if (application.isError) return <QueryError error={application.error} onRetry={() => application.refetch()} />

  const detail = application.data
  // While a run streams, show only its pieces; afterwards the saved pack (refetched) plus anything just received.
  const pieces: Pieces = generation.active ? generation.pieces : { ...savedPieces(detail.pieces), ...generation.pieces }
  const version = generation.runId ?? detail.latest_run?.id // which run's files to preview
  const hasPieces = Object.keys(pieces).length > 0
  const current = tab ?? (pieces.resume ? "resume" : "match_report")

  return (
    <>
      <Link href="/applications" className="mb-4 inline-flex h-10 items-center gap-1 rounded-md text-sm text-muted-foreground hover:text-foreground">
        <ChevronLeft className="size-4" aria-hidden /> Applications
      </Link>
      <PageHeader
        title={detail.job.title}
        description={
          <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
            {detail.job.company && <span>{detail.job.company}</span>}
            <span>Added {formatDate(detail.created_at)}</span>
            {detail.job.url && (
              <a href={detail.job.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-primary underline-offset-4 hover:underline">
                View posting <ExternalLink className="size-3.5" aria-hidden />
              </a>
            )}
          </span>
        }
        actions={<RunStatusBadge status={generation.active ? "running" : (detail.latest_run?.status ?? null)} />}
      />

      <div className="flex flex-col gap-8">
        <GeneratePanel applicationId={id} hasPack={hasPieces} />

        {(hasPieces || generation.active) && (
          <Tabs value={current} onValueChange={(value) => setTab(value as PieceKind)}>
            <TabsList className="w-full sm:w-fit">
              {TABS.map(({ kind, label }) => (
                <TabsTrigger key={kind} value={kind} className="px-2 sm:px-4">
                  {label}
                  {generation.active && !pieces[kind] && <Spinner className="size-3.5" />}
                </TabsTrigger>
              ))}
            </TabsList>
            <TabsContent value="match_report" className="pt-4">
              <Piece ready={pieces.match_report} writing={generation.active}>
                {(report) => <MatchReport report={report} job={job.data?.spec} />}
              </Piece>
            </TabsContent>
            <TabsContent value="resume" className="pt-4">
              <Piece ready={pieces.resume} writing={generation.active}>
                {(outcome) => <ResumePanel applicationId={id} outcome={outcome} version={version} />}
              </Piece>
            </TabsContent>
            <TabsContent value="cover_letter" className="pt-4">
              <Piece ready={pieces.cover_letter} writing={generation.active}>
                {(outcome) => <CoverLetterPanel applicationId={id} outcome={outcome} />}
              </Piece>
            </TabsContent>
            <TabsContent value="outreach" className="pt-4">
              <Piece ready={pieces.outreach} writing={generation.active}>
                {(outcome) => <OutreachPanel outcome={outcome} />}
              </Piece>
            </TabsContent>
          </Tabs>
        )}
      </div>
    </>
  )
}

/** A piece that's ready, still being written, or missing from the last pack (e.g. the AI failed partway). */
function Piece<T>({ ready, writing, children }: { ready: T | undefined; writing: boolean; children: (piece: T) => ReactNode }) {
  if (ready) return children(ready)
  if (writing) {
    return (
      <div className="flex flex-col gap-3" aria-busy="true">
        <p className="flex items-center gap-2 text-sm text-muted-foreground"><Spinner /> Writing this part…</p>
        <Skeleton className="h-6 w-3/4" />
        <Skeleton className="h-6 w-2/3" />
        <Skeleton className="h-6 w-5/6" />
      </div>
    )
  }
  return <p className="text-muted-foreground">This part isn&apos;t in the latest pack. Generate again to write it.</p>
}
