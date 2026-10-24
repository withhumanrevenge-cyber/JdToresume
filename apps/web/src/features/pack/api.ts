import { useEffect, useMemo } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"

import { api, unwrap } from "@/lib/api/client"
import { fetchFile, saveBlob } from "@/lib/api/files"

export type DocumentKind = "resume" | "cover_letter"
export type FileFormat = "pdf" | "docx"
export type Template = "classic" | "modern"

const FILE_NAMES: Record<DocumentKind, Record<FileFormat, string>> = {
  resume: { pdf: "resume.pdf", docx: "resume.docx" },
  cover_letter: { pdf: "cover-letter.pdf", docx: "cover-letter.docx" },
}

function filePath(applicationId: string, document: DocumentKind, format: FileFormat, template: Template) {
  return `/v1/applications/${applicationId}/files/${FILE_NAMES[document][format]}?template=${template}`
}

/**
 * "What the ATS sees" for one file: the text a parser reads back and the round-trip check. `version` (the run
 * id) is part of the key, so a newly generated pack is checked again instead of showing the old result.
 */
export function useAtsView(applicationId: string, document: DocumentKind, format: FileFormat, template: Template, version: string | undefined) {
  return useQuery({
    queryKey: ["ats", applicationId, document, format, template, version],
    queryFn: () =>
      unwrap(
        api.GET("/v1/applications/{application_id}/ats-check", {
          params: { path: { application_id: applicationId }, query: { document, format, template } },
        }),
      ),
    enabled: Boolean(version),
    staleTime: Infinity,
  })
}

/** The rendered PDF itself, so the preview is exactly what gets downloaded. */
export function usePdfPreview(applicationId: string, document: DocumentKind, template: Template, version: string | undefined) {
  return useQuery({
    queryKey: ["preview", applicationId, document, template, version],
    queryFn: async () => (await fetchFile(filePath(applicationId, document, "pdf", template), "preview.pdf")).blob,
    enabled: Boolean(version),
    staleTime: Infinity,
    gcTime: 60_000, // PDFs are big; don't keep old ones around
  })
}

export function useDownload(applicationId: string) {
  return useMutation({
    mutationFn: async ({ document, format, template }: { document: DocumentKind; format: FileFormat; template: Template }) => {
      const fallback = FILE_NAMES[document][format]
      const file = await fetchFile(filePath(applicationId, document, format, template), fallback)
      saveBlob(file.blob, file.filename)
      return file.filename
    },
  })
}

/** An object URL for a blob, released when the blob changes or the component goes away. */
export function useObjectUrl(blob: Blob | undefined): string | null {
  const url = useMemo(() => (blob ? URL.createObjectURL(blob) : null), [blob])
  useEffect(() => () => {
    if (url) URL.revokeObjectURL(url)
  }, [url])
  return url
}
