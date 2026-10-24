"use client"

import { useRef, useState, type FormEvent } from "react"
import { useRouter } from "next/navigation"
import { ArrowRight, Link2, TextQuote } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Field, FieldDescription, FieldError, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { useStartApplication } from "@/features/applications/api"
import { ApiError, errorMessage } from "@/lib/api/client"

type Source = "link" | "text"

const MAX_TEXT = 30_000
// Codes for links we can't read for the user; pasting the description always works (jd-ingestion skill).
const PASTE_INSTEAD = new Set(["client_only_source", "job_not_readable"])

/** Add a job by link or pasted description. Reading it takes the AI a few seconds, and the wait says so. */
export function JobIntake() {
  const router = useRouter()
  const start = useStartApplication()
  const [source, setSource] = useState<Source>("link")
  const [url, setUrl] = useState("")
  const [text, setText] = useState("")
  const [fieldError, setFieldError] = useState<string | null>(null)
  const textRef = useRef<HTMLTextAreaElement>(null)

  function submit(event: FormEvent) {
    event.preventDefault()
    const value = source === "link" ? url.trim() : text.trim()
    if (source === "link" && !/^(https?:\/\/)?[^\s.]+\.[^\s]+$/i.test(value)) {
      setFieldError("Paste the full link to the job posting.")
      return
    }
    if (source === "text" && value.length < 200) {
      setFieldError("That's too short to be a job description. Paste the whole posting.")
      return
    }
    setFieldError(null)
    start.mutate(source === "link" ? { url: value } : { text: value }, {
      onSuccess: (application) => router.push(`/applications/${application.id}`),
    })
  }

  function pasteInstead() {
    start.reset()
    setSource("text")
    requestAnimationFrame(() => textRef.current?.focus())
  }

  const apiError = start.isError ? start.error : null
  const error = fieldError ?? (apiError ? errorMessage(apiError) : null)
  const offerPaste = source === "link" && apiError instanceof ApiError && PASTE_INSTEAD.has(apiError.code)

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-6">
      <Tabs
        value={source}
        onValueChange={(value) => {
          setSource(value as Source)
          setFieldError(null)
          start.reset()
        }}
      >
        <TabsList className="w-full sm:w-fit">
          <TabsTrigger value="link"><Link2 aria-hidden /> Link</TabsTrigger>
          <TabsTrigger value="text"><TextQuote aria-hidden /> Paste description</TabsTrigger>
        </TabsList>

        <TabsContent value="link" className="pt-4">
          <Field data-invalid={error ? true : undefined}>
            <FieldLabel htmlFor="job-url">Job posting link</FieldLabel>
            <Input
              id="job-url"
              type="url"
              inputMode="url"
              autoComplete="url"
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              placeholder="https://boards.greenhouse.io/company/jobs/123"
              aria-invalid={error ? true : undefined}
              aria-describedby="job-url-hint"
            />
            <FieldDescription id="job-url-hint">
              Works with Greenhouse, Lever, Ashby and most company career pages. LinkedIn, Indeed and Naukri links
              can&apos;t be read for you: paste the description instead.
            </FieldDescription>
          </Field>
        </TabsContent>

        <TabsContent value="text" className="pt-4">
          <Field data-invalid={error ? true : undefined}>
            <FieldLabel htmlFor="job-text">Job description</FieldLabel>
            <Textarea
              ref={textRef}
              id="job-text"
              rows={12}
              maxLength={MAX_TEXT}
              value={text}
              onChange={(event) => setText(event.target.value)}
              placeholder="Paste the whole posting: title, company, responsibilities and requirements."
              aria-invalid={error ? true : undefined}
              aria-describedby="job-text-hint"
              className="min-h-56"
            />
            <FieldDescription id="job-text-hint">
              {text.length.toLocaleString()} / {MAX_TEXT.toLocaleString()} characters
            </FieldDescription>
          </Field>
        </TabsContent>
      </Tabs>

      {error && (
        <FieldError className="flex flex-col items-start gap-2">
          <span>{error}</span>
          {offerPaste && (
            <Button type="button" variant="outline" size="sm" onClick={pasteInstead}>
              <TextQuote aria-hidden /> Paste the description instead
            </Button>
          )}
        </FieldError>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" size="lg" disabled={start.isPending}>
          {start.isPending ? <Spinner /> : null}
          {start.isPending ? "Reading the job…" : "Add job"}
          {!start.isPending && <ArrowRight data-icon="inline-end" aria-hidden />}
        </Button>
        <p role="status" className="text-sm text-muted-foreground">
          {start.isPending ? "Pulling out the requirements and keywords. This takes a few seconds." : ""}
        </p>
      </div>
    </form>
  )
}
