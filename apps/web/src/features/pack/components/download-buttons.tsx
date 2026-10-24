"use client"

import { Download } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { useDownload, type DocumentKind, type FileFormat, type Template } from "@/features/pack/api"
import { errorMessage } from "@/lib/api/client"

const FORMATS: { format: FileFormat; label: string }[] = [
  { format: "pdf", label: "PDF" },
  { format: "docx", label: "Word" },
]

/** PDF for most portals, Word for the ones (and recruiters) that ask for it. Both pass the same ATS check. */
export function DownloadButtons({ applicationId, document, template, disabled }: {
  applicationId: string
  document: DocumentKind
  template: Template
  disabled?: boolean
}) {
  const download = useDownload(applicationId)
  const pendingFormat = download.isPending ? download.variables?.format : null
  return (
    <div className="flex flex-wrap gap-2">
      {FORMATS.map(({ format, label }, index) => (
        <Button
          key={format}
          variant={index === 0 ? "default" : "outline"}
          disabled={disabled || download.isPending}
          onClick={() =>
            download.mutate(
              { document, format, template },
              {
                onSuccess: (filename) => toast.success(`Downloaded ${filename}`),
                onError: (error) => toast.error(errorMessage(error)),
              },
            )
          }
        >
          {pendingFormat === format ? <Spinner /> : <Download aria-hidden />}
          {label}
        </Button>
      ))}
    </div>
  )
}
