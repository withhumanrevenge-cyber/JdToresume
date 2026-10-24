import Link from "next/link"
import { CircleAlert } from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"

/** Files carry the person's name and email at the top, so they can't be made until those exist. */
export function ContactNeeded() {
  return (
    <Alert variant="warning">
      <CircleAlert aria-hidden />
      <AlertTitle>Add your name and email to preview and download</AlertTitle>
      <AlertDescription>
        They go at the top of the document. <Link href="/profile">Add contact details</Link>
      </AlertDescription>
    </Alert>
  )
}
