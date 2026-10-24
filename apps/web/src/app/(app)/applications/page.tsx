import type { Metadata } from "next"

import { ApplicationsScreen } from "@/features/applications/components/applications-screen"

export const metadata: Metadata = { title: "Applications" }

export default function ApplicationsPage() {
  return <ApplicationsScreen />
}
