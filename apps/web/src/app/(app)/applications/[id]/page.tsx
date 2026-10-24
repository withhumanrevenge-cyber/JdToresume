import { Suspense } from "react"
import type { Metadata } from "next"

import { Skeleton } from "@/components/ui/skeleton"
import { ApplicationScreen } from "@/features/applications/components/application-screen"

export const metadata: Metadata = { title: "Application" }

export default function ApplicationPage({ params }: PageProps<"/applications/[id]">) {
  return (
    // The id is only known per request, so it's read inside Suspense and the rest of the page prerenders.
    <Suspense fallback={<Skeleton className="h-56 w-full rounded-xl" />}>
      <ApplicationFromParams params={params} />
    </Suspense>
  )
}

async function ApplicationFromParams({ params }: { params: PageProps<"/applications/[id]">["params"] }) {
  const { id } = await params
  return <ApplicationScreen id={id} />
}
