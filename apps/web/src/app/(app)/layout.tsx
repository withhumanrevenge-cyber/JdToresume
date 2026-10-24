import { Suspense, type ReactNode } from "react"

import { AppShell } from "@/components/app-shell"
import { FullPageStatus, SessionGate } from "@/features/auth/components/session-gate"

/**
 * Every signed-in page: the session gate, then the header and navigation around the page. The gate renders only in
 * the browser (the session is in browser storage), which is why instant-navigation checks are opt-in (next.config.ts).
 */
export default function SignedInLayout({ children }: { children: ReactNode }) {
  return (
    <Suspense fallback={<FullPageStatus label="Loading…" />}>
      <SessionGate>
        <AppShell>{children}</AppShell>
      </SessionGate>
    </Suspense>
  )
}
