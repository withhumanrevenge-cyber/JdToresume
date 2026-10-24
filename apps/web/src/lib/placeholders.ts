/**
 * The AI never sees contact details: it writes placeholders such as {{FULL_NAME}} or {{LINK_0}}, and they are put
 * back where the text is shown. The server does this for PDF and DOCX files (server/app/llm/pii.py); this is the
 * same substitution for text shown and copied in the browser, using the contact details the user already has.
 */
import type { Schemas } from "@/lib/api/client"

type Contact = Pick<Schemas["ContactOut"], "full_name" | "email" | "phone" | "city" | "links">

export function fillPlaceholders(text: string, contact: Contact | null | undefined): string {
  if (!contact) return text
  const values: Record<string, string> = {
    FULL_NAME: contact.full_name,
    EMAIL: contact.email,
    PHONE: contact.phone ?? "",
    CITY: contact.city ?? "",
  }
  contact.links.forEach((link, index) => {
    values[`LINK_${index}`] = link
  })
  return text.replace(/\{\{([A-Z_0-9]+)\}\}/g, (placeholder, name: string) => values[name] ?? placeholder)
}
