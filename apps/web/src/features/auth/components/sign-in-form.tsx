"use client"

import { useEffect, useId, useState, type FormEvent } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { ArrowRight } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Spinner } from "@/components/ui/spinner"
import { safeNextPath, useDevSignIn } from "@/features/auth/api"
import { errorMessage } from "@/lib/api/client"
import { useSession } from "@/lib/session"

const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/

export function SignInForm() {
  const session = useSession()
  const router = useRouter()
  const next = safeNextPath(useSearchParams().get("next"))
  const signIn = useDevSignIn()
  const [email, setEmail] = useState("")
  const [fieldError, setFieldError] = useState<string | null>(null)
  const errorId = useId()

  useEffect(() => {
    if (session) router.replace(next) // already signed in, or just signed in
  }, [session, next, router])

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const value = email.trim()
    if (!EMAIL_PATTERN.test(value)) {
      setFieldError("Enter an email address like you@example.com.")
      return
    }
    setFieldError(null)
    signIn.mutate(value)
  }

  const error = fieldError ?? (signIn.isError ? errorMessage(signIn.error) : null)

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <Label htmlFor="email">Email</Label>
        <Input
          id="email"
          type="email"
          inputMode="email"
          autoComplete="email"
          autoFocus
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? errorId : undefined}
          placeholder="you@example.com"
        />
        {error && (
          <p id={errorId} role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
      </div>
      <Button type="submit" size="lg" disabled={signIn.isPending || signIn.isSuccess}>
        {signIn.isPending ? <Spinner /> : null}
        Continue
        {!signIn.isPending && <ArrowRight data-icon="inline-end" aria-hidden />}
      </Button>
    </form>
  )
}
