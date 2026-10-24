"use client"

import type { ReactNode } from "react"

import { Badge } from "@/components/ui/badge"
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { useContact } from "@/features/profile/api"
import { CopyButton } from "@/features/pack/components/copy-button"
import type { Schemas } from "@/lib/api/client"
import { fillPlaceholders } from "@/lib/placeholders"

const LINKEDIN_NOTE_LIMIT = 200 // connection notes are cut off after this (resume-tailoring §6)

/** Ready-to-send messages, each with a copy button. Nothing is sent from Tailor itself. */
export function OutreachPanel({ outcome }: { outcome: Schemas["OutreachOutcome"] }) {
  const contact = useContact()
  const fill = (text: string) => fillPlaceholders(text, contact.data)
  const pack = outcome.outreach
  const note = fill(pack.linkedin_note)

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Message
        title="Email to the recruiter"
        description="Send from your own inbox."
        copyText={`Subject: ${fill(pack.recruiter_email_subject)}\n\n${fill(pack.recruiter_email_body)}`}
        className="lg:col-span-2"
      >
        <p className="font-medium">Subject: {fill(pack.recruiter_email_subject)}</p>
        <p className="whitespace-pre-line">{fill(pack.recruiter_email_body)}</p>
      </Message>
      <Message
        title="LinkedIn connection note"
        description={
          <span className="flex items-center gap-2">
            Fits the connection request box.
            <Badge variant={note.length > LINKEDIN_NOTE_LIMIT ? "warning" : "secondary"} className="tabular-nums">
              {note.length}/{LINKEDIN_NOTE_LIMIT}
            </Badge>
          </span>
        }
        copyText={note}
      >
        <p className="whitespace-pre-line">{note}</p>
      </Message>
      <Message title="Referral ask" description="For someone you know at the company." copyText={fill(pack.referral_ask)}>
        <p className="whitespace-pre-line">{fill(pack.referral_ask)}</p>
      </Message>
      <Message title="Follow-up" description="About a week after applying, if you haven't heard back." copyText={fill(pack.follow_up)} className="lg:col-span-2">
        <p className="whitespace-pre-line">{fill(pack.follow_up)}</p>
      </Message>
    </div>
  )
}

function Message({ title, description, copyText, className, children }: {
  title: string
  description: ReactNode
  copyText: string
  className?: string
  children: ReactNode
}) {
  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="font-semibold">{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
        <CardAction>
          <CopyButton text={copyText} />
        </CardAction>
      </CardHeader>
      <CardContent className="flex max-w-[70ch] flex-col gap-3 leading-relaxed">{children}</CardContent>
    </Card>
  )
}
