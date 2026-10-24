import { Badge } from "@/components/ui/badge"

const LOOK: Record<string, { label: string; variant: "secondary" | "success" | "destructive" | "warning" | "outline" }> = {
  running: { label: "Generating", variant: "secondary" },
  succeeded: { label: "Pack ready", variant: "success" },
  failed: { label: "Failed", variant: "destructive" },
  cancelled: { label: "Stopped", variant: "warning" },
}

/** Where an application's latest pack stands, in words (the colour only repeats it). `null` = never generated. */
export function RunStatusBadge({ status }: { status: string | null }) {
  const look = status ? (LOOK[status] ?? { label: status, variant: "outline" as const }) : { label: "Not generated", variant: "outline" as const }
  return <Badge variant={look.variant}>{look.label}</Badge>
}
