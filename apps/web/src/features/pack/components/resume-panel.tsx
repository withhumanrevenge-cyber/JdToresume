"use client"

import { useState } from "react"
import { ExternalLink, ShieldCheck } from "lucide-react"

import { QueryError } from "@/components/query-error"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { useContact } from "@/features/profile/api"
import { useAtsView, useObjectUrl, usePdfPreview, type Template } from "@/features/pack/api"
import { AtsSummary, AtsText } from "@/features/pack/components/ats-report"
import { ContactNeeded } from "@/features/pack/components/contact-needed"
import { DownloadButtons } from "@/features/pack/components/download-buttons"
import type { Schemas } from "@/lib/api/client"

/**
 * The tailored resume as the real rendered PDF (what you see is what you download), the measured ATS check, and
 * the plain text a parser reads. `version` is the run that wrote it, so a new pack loads fresh files.
 */
export function ResumePanel({ applicationId, outcome, version }: {
  applicationId: string
  outcome: Schemas["ResumeOutcome"]
  version: string | undefined
}) {
  const [template, setTemplate] = useState<Template>("classic")
  const contact = useContact()
  const ready = Boolean(contact.data) ? version : undefined // files need a name and email
  const ats = useAtsView(applicationId, "resume", "pdf", template, ready)

  if (contact.isSuccess && !contact.data) return <ContactNeeded />

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <ToggleGroup
          type="single"
          variant="outline"
          value={template}
          onValueChange={(value) => value && setTemplate(value as Template)}
          aria-label="Resume layout"
        >
          <ToggleGroupItem value="classic">Classic</ToggleGroupItem>
          <ToggleGroupItem value="modern">Modern</ToggleGroupItem>
        </ToggleGroup>
        <DownloadButtons applicationId={applicationId} document="resume" template={template} disabled={!ready} />
      </div>

      {outcome.revised && (
        <p className="flex items-start gap-2 text-sm text-muted-foreground">
          <ShieldCheck className="mt-0.5 size-4 shrink-0 text-success" aria-hidden />
          A second check found claims your profile didn&apos;t support in the first draft, and they were rewritten.
        </p>
      )}

      {ats.isPending ? (
        <Skeleton className="h-40 w-full rounded-xl" />
      ) : ats.isError ? (
        <QueryError error={ats.error} onRetry={() => ats.refetch()} title="The ATS check didn't run" />
      ) : (
        <AtsSummary view={ats.data} />
      )}

      <Tabs defaultValue="preview">
        <TabsList>
          <TabsTrigger value="preview">Preview</TabsTrigger>
          <TabsTrigger value="ats">What the ATS sees</TabsTrigger>
        </TabsList>
        <TabsContent value="preview" className="pt-3">
          <PdfPreview applicationId={applicationId} template={template} version={ready} />
        </TabsContent>
        <TabsContent value="ats" className="pt-3">
          {ats.data ? <AtsText view={ats.data} /> : <Skeleton className="h-96 w-full rounded-xl" />}
        </TabsContent>
      </Tabs>
    </div>
  )
}

function PdfPreview({ applicationId, template, version }: { applicationId: string; template: Template; version: string | undefined }) {
  const preview = usePdfPreview(applicationId, "resume", template, version)
  const url = useObjectUrl(preview.data)

  if (preview.isError) return <QueryError error={preview.error} onRetry={() => preview.refetch()} title="The preview didn't load" />
  if (!url) return <Skeleton className="aspect-[8.5/11] w-full max-w-3xl rounded-xl" />
  return (
    <div className="flex flex-col gap-2">
      <iframe src={url} title="Resume preview (PDF)" className="aspect-[8.5/11] max-h-[85dvh] w-full max-w-3xl rounded-xl border bg-white" />
      <a href={url} target="_blank" rel="noopener noreferrer" className="inline-flex h-10 items-center gap-1.5 self-start text-sm text-primary underline-offset-4 hover:underline">
        Open the PDF in a new tab <ExternalLink className="size-4" aria-hidden />
      </a>
    </div>
  )
}
