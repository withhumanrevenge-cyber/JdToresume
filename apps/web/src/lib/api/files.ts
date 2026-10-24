/**
 * Authenticated file downloads. A plain <a href> can't send the Authorization header, so files are fetched as
 * blobs and saved (or previewed) from an object URL, under the name the server chose.
 */
import { API_URL, NETWORK_ERROR, authHeaders, toApiError } from "@/lib/api/client"

export type DownloadedFile = {
  blob: Blob
  filename: string
  headers: Headers
}

export async function fetchFile(path: string, fallbackName: string): Promise<DownloadedFile> {
  let response: Response
  try {
    response = await fetch(`${API_URL}${path}`, { headers: authHeaders() })
  } catch {
    throw NETWORK_ERROR
  }
  if (!response.ok) throw toApiError(response.status, await response.json().catch(() => null))
  const filename = filenameFromDisposition(response.headers.get("Content-Disposition"), fallbackName)
  return { blob: await response.blob(), filename, headers: response.headers }
}

/** The file name from a Content-Disposition header: the UTF-8 `filename*` if present, else `filename`. */
export function filenameFromDisposition(header: string | null, fallback: string): string {
  if (!header) return fallback
  const extended = /filename\*\s*=\s*UTF-8''([^;]+)/i.exec(header)
  if (extended) {
    try {
      return decodeURIComponent(extended[1].trim())
    } catch {
      // malformed encoding: use the plain name below
    }
  }
  const plain = /filename\s*=\s*"([^"]*)"/i.exec(header) ?? /filename\s*=\s*([^;]+)/i.exec(header)
  return plain?.[1].trim() || fallback
}

/** Hand a blob to the browser as a download. */
export function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = filename
  document.body.append(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 10_000) // give the download time to start
}
