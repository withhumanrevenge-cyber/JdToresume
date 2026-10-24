"use client"

import type { ReactNode } from "react"
import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { useQueryClient } from "@tanstack/react-query"
import { BriefcaseBusiness, CircleUserRound, LogOut, Monitor, Moon, Scissors, Sun, UserRound } from "lucide-react"
import { useTheme } from "next-themes"
import { cn } from "cn"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuRadioGroup,
  DropdownMenuRadioItem, DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { signOut } from "@/features/auth/api"
import { allowanceSummary, usePlan } from "@/features/billing/api"
import { useSession } from "@/lib/session"

const NAV = [
  { href: "/applications", label: "Applications", icon: BriefcaseBusiness },
  { href: "/profile", label: "Profile", icon: UserRound },
  { href: "/account", label: "Account", icon: CircleUserRound },
] as const

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <>
      <header className="sticky top-0 z-40 border-b bg-background">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 px-4 sm:px-6">
          <Brand />
          <MainNav />
          <div className="ml-auto flex h-16 items-center gap-1 sm:gap-2">
            <PlanChip />
            <ThemeMenu />
            <UserMenu />
          </div>
        </div>
      </header>
      <main id="main" tabIndex={-1} className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 outline-none sm:px-6 sm:py-10">
        {children}
      </main>
    </>
  )
}

export function Brand() {
  return (
    <Link href="/applications" className="flex h-16 items-center gap-2 rounded-md font-semibold tracking-tight">
      <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
        <Scissors className="size-4" aria-hidden />
      </span>
      <span className="text-lg">Tailor</span>
    </Link>
  )
}

function MainNav() {
  const pathname = usePathname()
  return (
    // Below md the nav takes its own row under the brand and actions; from md up it sits between them.
    <nav aria-label="Main" className="order-last -mx-1 flex w-full gap-1 pb-2 md:order-none md:mx-0 md:w-auto md:pb-0">
      {NAV.map(({ href, label, icon: Icon }) => {
        const active = pathname === href || pathname.startsWith(`${href}/`)
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex h-10 flex-1 items-center justify-center gap-2 rounded-lg px-3 text-sm font-medium transition-colors md:flex-none",
              "focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none",
              active ? "bg-secondary text-secondary-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground",
            )}
          >
            <Icon className="size-4" aria-hidden />
            {label}
          </Link>
        )
      })}
    </nav>
  )
}

function PlanChip() {
  const { data: plan } = usePlan()
  if (!plan) return null
  const empty = plan.next_pack_mode === null
  return (
    <Link
      href="/account"
      className={cn(
        "hidden h-9 items-center rounded-full border px-3 text-xs font-medium transition-colors sm:flex",
        "focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none",
        empty ? "border-transparent bg-warning-muted text-warning-muted-foreground" : "text-muted-foreground hover:bg-muted",
      )}
    >
      {empty ? "No packs left" : allowanceSummary(plan)}
    </Link>
  )
}

function ThemeMenu() {
  const { theme, setTheme } = useTheme()
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="Colour theme">
          <Sun className="dark:hidden" aria-hidden />
          <Moon className="hidden dark:block" aria-hidden />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel>Theme</DropdownMenuLabel>
        <DropdownMenuRadioGroup value={theme ?? "system"} onValueChange={setTheme}>
          <DropdownMenuRadioItem value="light"><Sun aria-hidden /> Light</DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="dark"><Moon aria-hidden /> Dark</DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="system"><Monitor aria-hidden /> System</DropdownMenuRadioItem>
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function UserMenu() {
  const session = useSession()
  const queryClient = useQueryClient()
  const router = useRouter()
  // Signing out needs no navigation here: the session gate sees the session end and shows the sign-in page.
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="Account menu">
          <CircleUserRound aria-hidden />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-56">
        <DropdownMenuLabel className="truncate font-normal text-muted-foreground">{session?.email}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => router.push("/account")}>
          <CircleUserRound aria-hidden /> Account and plan
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => signOut(queryClient)}>
          <LogOut aria-hidden /> Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
