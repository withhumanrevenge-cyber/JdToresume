import type { Metadata } from "next"
import Link from "next/link"
import { ChevronLeft } from "lucide-react"

import { PageHeader } from "@/components/page-header"
import { Card, CardContent } from "@/components/ui/card"
import { JobIntake } from "@/features/applications/components/job-intake"

export const metadata: Metadata = { title: "New application" }

export default function NewApplicationPage() {
  return (
    <div className="mx-auto w-full max-w-3xl">
      <Link href="/applications" className="mb-4 inline-flex h-10 items-center gap-1 rounded-md text-sm text-muted-foreground hover:text-foreground">
        <ChevronLeft className="size-4" aria-hidden /> Applications
      </Link>
      <PageHeader title="New application" description="Add the job you want to apply for. You'll generate the pack on the next screen." />
      <Card>
        <CardContent>
          <JobIntake />
        </CardContent>
      </Card>
    </div>
  )
}
