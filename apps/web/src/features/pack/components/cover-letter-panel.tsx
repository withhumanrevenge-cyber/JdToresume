"use client"

import { Card, CardContent } from "@/components/ui/card"
import { useContact } from "@/features/profile/api"
import { ContactNeeded } from "@/features/pack/components/contact-needed"
import { CopyButton } from "@/features/pack/components/copy-button"
import { DownloadButtons } from "@/features/pack/components/download-buttons"
import type { Schemas } from "@/lib/api/client"
import { fillPlaceholders } from "@/lib/placeholders"

/** The letter as text to read and copy (real name and links filled in), plus PDF and Word downloads. */
export function CoverLetterPanel({ applicationId, outcome }: { applicationId: string; outcome: Schemas["CoverLetterOutcome"] }) {
  const contact = useContact()
  const fill = (text: string) => fillPlaceholders(text, contact.data)
  const letter = outcome.letter
  const signature = contact.data?.full_name ?? ""
  const plainText = [fill(letter.salutation), ...letter.paragraphs.map(fill), `${fill(letter.closing)}\n${signature}`].join("\n\n").trim()

  return (
    <div className="flex flex-col gap-6">
      {contact.isSuccess && !contact.data ? (
        <ContactNeeded />
      ) : (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <DownloadButtons applicationId={applicationId} document="cover_letter" template="classic" disabled={!contact.data} />
          <CopyButton text={plainText} label="Copy text" />
        </div>
      )}
      <Card>
        <CardContent>
          {/* A readable measure (about 70 characters), like the letter itself. */}
          <article aria-label="Cover letter" className="flex max-w-[70ch] flex-col gap-4 leading-relaxed">
            <p>{fill(letter.salutation)}</p>
            {letter.paragraphs.map((paragraph, index) => (
              <p key={index}>{fill(paragraph)}</p>
            ))}
            <p className="whitespace-pre-line">{`${fill(letter.closing)}\n${signature}`}</p>
          </article>
        </CardContent>
      </Card>
    </div>
  )
}
