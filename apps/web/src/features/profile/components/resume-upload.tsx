"use client"

import { useId, useRef, useState, type DragEvent } from "react"
import { FileUp } from "lucide-react"
import { toast } from "sonner"
import { cn } from "cn"

import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { useUploadResume } from "@/features/profile/api"
import { errorMessage } from "@/lib/api/client"

const ACCEPTED = [".pdf", ".txt", ".md"]
const MAX_BYTES = 5 * 1024 * 1024

function problemWith(file: File): string | null {
  const name = file.name.toLowerCase()
  if (!ACCEPTED.some((extension) => name.endsWith(extension))) return "Upload a PDF, TXT or MD file."
  if (file.size > MAX_BYTES) return "That file is over 5 MB. Export a smaller PDF and try again."
  return null
}

/**
 * Pick or drop a resume. Dropping is a shortcut only: the button works with a mouse, keyboard or screen reader.
 * Reading the file takes the AI 10–30 seconds, so the wait is explained rather than shown as a bare spinner.
 */
export function ResumeUpload({ variant = "full" }: { variant?: "full" | "compact" }) {
  const upload = useUploadResume()
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [problem, setProblem] = useState<string | null>(null)
  const hintId = useId()

  function send(file: File | undefined) {
    if (!file || upload.isPending) return
    const issue = problemWith(file)
    setProblem(issue)
    if (issue) return
    upload.mutate(file, {
      onSuccess: (result) =>
        toast.success(`Profile updated to version ${result.profile.version}`, {
          description:
            result.facts_without_numbers > 0
              ? `${result.facts_without_numbers} achievements have no numbers yet. Adding them makes stronger bullets.`
              : undefined,
        }),
    })
  }

  function onDrop(event: DragEvent) {
    event.preventDefault()
    setDragging(false)
    send(event.dataTransfer.files[0])
  }

  const error = problem ?? (upload.isError ? errorMessage(upload.error) : null)
  const picker = (
    <>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED.join(",")}
        className="sr-only"
        tabIndex={-1}
        aria-hidden
        onChange={(event) => {
          send(event.target.files?.[0])
          event.target.value = "" // picking the same file again should upload again
        }}
      />
      <Button
        type="button"
        size={variant === "full" ? "lg" : "default"}
        variant={variant === "full" ? "default" : "outline"}
        disabled={upload.isPending}
        aria-describedby={hintId}
        onClick={() => inputRef.current?.click()}
      >
        {upload.isPending ? <Spinner /> : <FileUp aria-hidden />}
        {upload.isPending ? "Reading your resume…" : variant === "full" ? "Choose your resume" : "Upload a newer resume"}
      </Button>
    </>
  )

  if (variant === "compact") {
    return (
      <div className="flex flex-col items-start gap-2">
        {picker}
        <p id={hintId} className="text-xs text-muted-foreground">PDF, TXT or MD, up to 5 MB</p>
        {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      </div>
    )
  }

  return (
    <div
      onDragOver={(event) => {
        event.preventDefault()
        setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      className={cn(
        "flex flex-col items-center gap-4 rounded-xl border-2 border-dashed border-input px-6 py-12 text-center transition-colors",
        dragging && "border-primary bg-secondary",
      )}
    >
      <span className="flex size-12 items-center justify-center rounded-full bg-secondary text-secondary-foreground">
        <FileUp className="size-6" aria-hidden />
      </span>
      <div className="flex flex-col gap-1">
        <p className="font-medium">Upload the resume you use today</p>
        <p id={hintId} className="text-sm text-muted-foreground">
          PDF, TXT or MD, up to 5 MB. Drop it here or choose a file.
        </p>
      </div>
      {picker}
      <p role="status" className="min-h-5 text-sm text-muted-foreground">
        {upload.isPending ? "This usually takes 10–30 seconds. Your contact details stay out of the AI." : ""}
      </p>
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    </div>
  )
}
