"use client"

import { Download, Trash2 } from "lucide-react"
import { toast } from "sonner"

import { PageHeader } from "@/components/page-header"
import { QueryError } from "@/components/query-error"
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { useDeleteAccount, useExportData } from "@/features/account/api"
import { usePlan } from "@/features/billing/api"
import { errorMessage, type Schemas } from "@/lib/api/client"
import { formatDate } from "@/lib/format"
import { useSession } from "@/lib/session"

// The paid plans (COSTS §3), shown for reference until payments are switched on.
const PAID_PLANS = [
  { name: "Sprint pass", price: "$12 / 7 days", detail: "One-time. Quick and Deep, all templates." },
  { name: "Pro monthly", price: "$24 / month", detail: "Cancel any time, in one click." },
  { name: "Pro quarter", price: "$59 / 90 days", detail: "Most job searches take 3–4 months." },
]

export function AccountScreen() {
  const session = useSession()
  return (
    <>
      <PageHeader title="Account" description={session ? `Signed in as ${session.email}` : undefined} />
      <div className="flex flex-col gap-6">
        <PlanCard />
        <DataCard />
        <DeleteCard />
      </div>
    </>
  )
}

function PlanCard() {
  const plan = usePlan()
  if (plan.isPending) return <Skeleton className="h-64 w-full rounded-xl" />
  if (plan.isError) return <QueryError error={plan.error} onRetry={() => plan.refetch()} />
  return <PlanDetails plan={plan.data} />
}

function PlanDetails({ plan }: { plan: Schemas["PlanOut"] }) {
  const { used, limit, window, resets_at: resetsAt } = plan.packs
  const free = plan.plan === "free"
  const windowText = window === "calendar_month" ? "this month" : "in the last 7 days"
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg font-semibold">
          {plan.name}
          {plan.deep_included && <Badge variant="secondary">Deep included</Badge>}
        </CardTitle>
        <CardDescription>
          {plan.expires_at ? `Active until ${formatDate(plan.expires_at)}.` : "3 Quick packs every month, free."}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-6">
        <div className="flex flex-col gap-2">
          <div className="flex items-baseline justify-between gap-4 text-sm">
            <span className="font-medium">{free ? "Free packs used" : "Packs used (fair use)"}</span>
            <span className="tabular-nums text-muted-foreground">{used} of {limit} {windowText}</span>
          </div>
          <Progress value={(Math.min(used, limit) / limit) * 100} aria-label={`${used} of ${limit} packs used ${windowText}`} className="h-2" />
          {resetsAt && (
            <p className="text-sm text-muted-foreground">
              {free ? `Your free packs come back on ${formatDate(resetsAt)}.` : `The oldest pack leaves the 7-day window on ${formatDate(resetsAt)}.`}
            </p>
          )}
        </div>

        <p className="text-sm">
          <span className="font-medium tabular-nums">{plan.deep_credits}</span> Deep {plan.deep_credits === 1 ? "pack" : "packs"} on top of your plan
          <span className="text-muted-foreground"> (one comes with every new account).</span>
        </p>

        {free && (
          <section className="flex flex-col gap-3">
            <h2 className="text-sm font-semibold">Paid plans</h2>
            <ul className="grid gap-3 sm:grid-cols-3">
              {PAID_PLANS.map((paid) => (
                <li key={paid.name} className="rounded-xl border p-4">
                  <p className="font-medium">{paid.name}</p>
                  <p className="text-lg font-semibold tabular-nums">{paid.price}</p>
                  <p className="text-sm text-muted-foreground">{paid.detail}</p>
                </li>
              ))}
            </ul>
            <p className="text-sm text-muted-foreground">
              Payments open soon. No trials that turn into charges, a reminder before every renewal, and a 7-day refund.
            </p>
          </section>
        )}
      </CardContent>
    </Card>
  )
}

function DataCard() {
  const exportData = useExportData()
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg font-semibold">Your data</CardTitle>
        <CardDescription>
          Download everything we store about you: profile versions, contact details, jobs, every generated pack and
          your usage, as one JSON file.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Button
          variant="outline"
          disabled={exportData.isPending}
          onClick={() =>
            exportData.mutate(undefined, {
              onSuccess: (filename) => toast.success(`Downloaded ${filename}`),
              onError: (error) => toast.error(errorMessage(error)),
            })
          }
        >
          {exportData.isPending ? <Spinner /> : <Download aria-hidden />}
          Download my data
        </Button>
      </CardContent>
    </Card>
  )
}

function DeleteCard() {
  const remove = useDeleteAccount()
  return (
    <Card className="ring-destructive/30">
      <CardHeader>
        <CardTitle className="text-lg font-semibold">Delete account</CardTitle>
        <CardDescription>
          Removes your account, profile, contact details, applications and packs for good. Download your data first if
          you want a copy.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button variant="destructive"><Trash2 aria-hidden /> Delete my account</Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Delete your account and all your data?</AlertDialogTitle>
              <AlertDialogDescription>This can&apos;t be undone. You can sign up again later, but nothing will be restored.</AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Keep my account</AlertDialogCancel>
              <AlertDialogAction
                variant="destructive"
                disabled={remove.isPending}
                onClick={(event) => {
                  event.preventDefault() // keep the dialog open until the server confirms
                  // On success the session ends and the session gate shows the sign-in page.
                  remove.mutate(undefined, {
                    onSuccess: () => toast.success("Your account and data were deleted"),
                    onError: (error) => toast.error(errorMessage(error)),
                  })
                }}
              >
                {remove.isPending && <Spinner />}
                Delete everything
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </CardContent>
    </Card>
  )
}
