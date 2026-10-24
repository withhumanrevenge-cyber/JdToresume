"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"

import { FullPageStatus } from "@/features/auth/components/session-gate"
import { useSession } from "@/lib/session"

export function HomeRedirect() {
  const session = useSession()
  const router = useRouter()
  useEffect(() => {
    router.replace(session ? "/applications" : "/sign-in")
  }, [session, router])
  return <FullPageStatus label="Loading…" />
}
