import { Suspense } from "react"
import type { Metadata } from "next"
import { FileCheck2, MailCheck, ShieldCheck } from "lucide-react"

import { Brand } from "@/components/app-shell"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { SignInForm } from "@/features/auth/components/sign-in-form"

export const metadata: Metadata = { title: "Sign in" }

const POINTS = [
  { icon: FileCheck2, text: "A resume tailored to each job, checked the way an ATS reads it" },
  { icon: ShieldCheck, text: "Every line comes from your own experience. Nothing is made up" },
  { icon: MailCheck, text: "Cover letter, recruiter email and LinkedIn note in the same pass" },
]

export default function SignInPage() {
  return (
    <main id="main" className="mx-auto grid w-full max-w-5xl flex-1 items-center gap-10 px-4 py-10 sm:px-6 md:grid-cols-2">
      <section className="flex flex-col gap-6">
        <Brand />
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Apply to every job with materials made for it</h1>
        <ul className="flex flex-col gap-4">
          {POINTS.map(({ icon: Icon, text }) => (
            <li key={text} className="flex items-start gap-3 text-muted-foreground">
              <Icon className="mt-0.5 size-5 shrink-0 text-primary" aria-hidden />
              <span>{text}</span>
            </li>
          ))}
        </ul>
      </section>

      <Card className="w-full max-w-md justify-self-center md:justify-self-end">
        <CardHeader>
          <CardTitle className="text-xl font-semibold">Sign in</CardTitle>
          <CardDescription>
            Development sign-in: enter any email to continue as that person. Google, LinkedIn and email links arrive
            with the real sign-in.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Suspense fallback={<Skeleton className="h-[7.5rem] w-full" />}>
            <SignInForm />
          </Suspense>
        </CardContent>
      </Card>
    </main>
  )
}
