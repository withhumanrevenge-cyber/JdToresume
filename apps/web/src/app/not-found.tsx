import Link from "next/link"

import { Brand } from "@/components/app-shell"
import { Button } from "@/components/ui/button"

export default function NotFound() {
  return (
    <main id="main" className="mx-auto flex w-full max-w-md flex-1 flex-col items-center justify-center gap-6 px-4 py-16 text-center">
      <Brand />
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">This page doesn&apos;t exist</h1>
        <p className="text-muted-foreground">The link may be old, or the application was deleted.</p>
      </div>
      <Button asChild size="lg">
        <Link href="/applications">Go to your applications</Link>
      </Button>
    </main>
  )
}
