"use client"

import { useEffect, type ReactNode } from "react"
import { usePathname, useRouter } from "next/navigation"

import { Spinner } from "@/components/ui/spinner"
import { sessionEndedByUser, useSession } from "@/lib/session"

/**
 * Renders its children only for a signed-in user. Anyone else goes to sign-in, and comes back to this page
 * afterwards, unless they just signed out on purpose.
 */
export function SessionGate({ children }: { children: ReactNode }) {
  const session = useSession()
  const router = useRouter()
  const pathname = usePathname()

  useEffect(() => {
    if (session) return
    router.replace(sessionEndedByUser() ? "/sign-in" : `/sign-in?next=${encodeURIComponent(pathname)}`)
  }, [session, pathname, router])

  if (!session) return <FullPageStatus label="Taking you to sign in…" />
  return children
}

export function FullPageStatus({ label }: { label: string }) {
  return (
    <div role="status" className="flex flex-1 items-center justify-center gap-3 p-8 text-muted-foreground">
      <Spinner />
      <span>{label}</span>
    </div>
  )
}
