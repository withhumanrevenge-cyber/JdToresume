"use client"

import { useQueryClient } from "@tanstack/react-query"
import { CircleAlert } from "lucide-react"

import { PageHeader } from "@/components/page-header"
import { QueryError } from "@/components/query-error"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { detectedContactKey, useContact, useProfile } from "@/features/profile/api"
import { ContactForm } from "@/features/profile/components/contact-form"
import { ProfileOverview } from "@/features/profile/components/profile-overview"
import { ResumeUpload } from "@/features/profile/components/resume-upload"
import type { Schemas } from "@/lib/api/client"
import { formatDate } from "@/lib/format"

export function ProfileScreen() {
  const profile = useProfile()
  const contact = useContact()
  const detected = useQueryClient().getQueryData<Schemas["ContactDetails"]>(detectedContactKey)

  return (
    <>
      <PageHeader title="Your profile" description="Everything Tailor writes comes from here, so nothing is made up." />

      {profile.isPending || contact.isPending ? (
        <div className="flex flex-col gap-6">
          <Skeleton className="h-64 w-full rounded-xl" />
          <Skeleton className="h-96 w-full rounded-xl" />
        </div>
      ) : profile.isError || contact.isError ? (
        <QueryError error={profile.error ?? contact.error} onRetry={() => (profile.isError ? profile.refetch() : contact.refetch())} />
      ) : (
        <div className="flex flex-col gap-6">
          {!profile.data && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg font-semibold">Start with your resume</CardTitle>
                <CardDescription>
                  We turn it into a list of facts about your work. Each tailored resume uses only those facts.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ResumeUpload />
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle className="text-lg font-semibold">Contact details</CardTitle>
              <CardDescription>The header of every resume and cover letter you download.</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-5">
              {!contact.data && profile.data && (
                <Alert>
                  <CircleAlert aria-hidden />
                  <AlertTitle>Add your name and email</AlertTitle>
                  <AlertDescription>Downloads need them. Check what we found in your resume and save.</AlertDescription>
                </Alert>
              )}
              {/* Remount when the saved details change elsewhere (an upload), so the form shows them. */}
              <ContactForm
                key={contact.data?.updated_at ?? (detected ? "detected" : "new")}
                contact={contact.data ?? detected ?? null}
              />
            </CardContent>
          </Card>

          {profile.data && (
            <Card>
              <CardHeader className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div className="flex flex-col gap-1.5">
                  <CardTitle className="flex items-center gap-2 text-lg font-semibold">
                    What we read from your resume
                    <Badge variant="secondary">Version {profile.data.version}</Badge>
                  </CardTitle>
                  <CardDescription>Updated {formatDate(profile.data.created_at)}. Upload again whenever your resume changes.</CardDescription>
                </div>
                <ResumeUpload variant="compact" />
              </CardHeader>
              <CardContent>
                <ProfileOverview profile={profile.data.profile} />
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </>
  )
}
