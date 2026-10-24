/** Display formatting. Dates show in the user's own locale and time zone. */

const dateFormat = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", year: "numeric" })
const dateTimeFormat = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" })

export function formatDate(iso: string): string {
  return dateFormat.format(new Date(iso))
}

export function formatDateTime(iso: string): string {
  return dateTimeFormat.format(new Date(iso))
}

/** "Mar 2022" from a profile's "2022-03"; a year on its own stays as it is. */
export function formatMonth(value: string | null): string {
  if (!value) return "Present"
  const [year, month] = value.split("-")
  if (!month) return year
  return new Intl.DateTimeFormat(undefined, { month: "short", year: "numeric" }).format(new Date(Number(year), Number(month) - 1))
}

export function formatPercent(share: number): string {
  return `${Math.round(share * 100)}%`
}
