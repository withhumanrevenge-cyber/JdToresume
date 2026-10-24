"use client"

import Link from "next/link"
import { BriefcaseBusiness, ChevronRight, Plus } from "lucide-react"

import { PageHeader } from "@/components/page-header"
import { QueryError } from "@/components/query-error"
import { Button } from "@/components/ui/button"
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { useApplications } from "@/features/applications/api"
import { RunStatusBadge } from "@/features/applications/components/run-status-badge"
import { formatDate } from "@/lib/format"

export function ApplicationsScreen() {
  const applications = useApplications()
  const items = applications.data?.pages.flatMap((page) => page.items) ?? []

  const newButton = (
    <Button asChild size="lg">
      <Link href="/applications/new">
        <Plus aria-hidden /> New application
      </Link>
    </Button>
  )

  return (
    <>
      <PageHeader
        title="Applications"
        description="One per job. Each gets its own resume, cover letter and outreach."
        actions={items.length > 0 ? newButton : undefined} // an empty list has its own button: one primary action
      />

      {applications.isPending ? (
        <div className="flex flex-col gap-3">
          {[0, 1, 2].map((key) => (
            <Skeleton key={key} className="h-20 w-full rounded-xl" />
          ))}
        </div>
      ) : applications.isError ? (
        <QueryError error={applications.error} onRetry={() => applications.refetch()} />
      ) : items.length === 0 ? (
        <Empty className="border bg-card py-16">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <BriefcaseBusiness aria-hidden />
            </EmptyMedia>
            <EmptyTitle>No applications yet</EmptyTitle>
            <EmptyDescription>Add a job by link or by pasting its description, and Tailor writes the pack for it.</EmptyDescription>
          </EmptyHeader>
          <EmptyContent>{newButton}</EmptyContent>
        </Empty>
      ) : (
        <>
          <ul className="flex flex-col gap-3">
            {items.map((application) => (
              <li key={application.id}>
                <Link
                  href={`/applications/${application.id}`}
                  className="group flex items-center gap-4 rounded-xl border bg-card p-4 transition-colors hover:border-primary/40 hover:bg-accent/40 focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none sm:p-5"
                >
                  <div className="flex min-w-0 flex-1 flex-col gap-1">
                    <p className="truncate font-medium">{application.job.title}</p>
                    <p className="truncate text-sm text-muted-foreground">
                      {[application.job.company, `added ${formatDate(application.created_at)}`].filter(Boolean).join(" · ")}
                    </p>
                  </div>
                  <RunStatusBadge status={application.latest_run?.status ?? null} />
                  <ChevronRight className="size-5 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" aria-hidden />
                </Link>
              </li>
            ))}
          </ul>
          {applications.hasNextPage && (
            <div className="mt-6 flex justify-center">
              <Button variant="outline" onClick={() => applications.fetchNextPage()} disabled={applications.isFetchingNextPage}>
                {applications.isFetchingNextPage && <Spinner />}
                Show older applications
              </Button>
            </div>
          )}
        </>
      )}
    </>
  )
}
