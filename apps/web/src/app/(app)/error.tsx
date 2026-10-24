"use client" // error boundaries must be Client Components

import { useEffect } from "react"
import Link from "next/link"
import { CircleAlert, RotateCw } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"

/** A page that crashed while rendering. The header and navigation stay usable; only this page is replaced. */
export default function PageError({ error, retry }: { error: unknown; retry: () => void }) {
  useEffect(() => {
    console.error(error) // Sentry picks this up once it's wired in (ARCHITECTURE §13)
  }, [error])

  return (
    <Empty className="border bg-card py-16">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <CircleAlert aria-hidden />
        </EmptyMedia>
        <EmptyTitle>This page hit a problem</EmptyTitle>
        <EmptyDescription>Nothing you saved is lost. Try again, or go back to your applications.</EmptyDescription>
      </EmptyHeader>
      <EmptyContent className="flex-row flex-wrap justify-center gap-2">
        <Button onClick={() => retry()}><RotateCw aria-hidden /> Try again</Button>
        <Button variant="outline" asChild><Link href="/applications">Applications</Link></Button>
      </EmptyContent>
    </Empty>
  )
}
