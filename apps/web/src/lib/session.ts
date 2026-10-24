/**
 * The signed-in session, kept in this browser's localStorage.
 *
 * Today it holds a development token from POST /v1/dev/sign-in; Better Auth replaces that (ARCHITECTURE §12) and
 * only this file changes. Components read it with `useSession()`, which renders only in the browser: the server
 * never sees the token, so the first render can't match server HTML (React's `browser()` handles that).
 */
import { use, useSyncExternalStore } from "react"
import { browser } from "react-dom"

export type Session = {
  token: string
  email: string
  expiresAt: string // ISO timestamp
}

const STORAGE_KEY = "tailor.session"
const listeners = new Set<() => void>()

// useSyncExternalStore needs the same object back while nothing changed, so parsing is cached by the raw string.
let cachedRaw: string | null | undefined
let cachedSession: Session | null = null

function storedRaw(): string | null {
  try {
    return window.localStorage.getItem(STORAGE_KEY)
  } catch {
    return null // storage blocked (private mode, browser policy)
  }
}

function parse(raw: string | null): Session | null {
  if (!raw) return null
  try {
    const value = JSON.parse(raw) as Partial<Session>
    if (typeof value.token === "string" && typeof value.email === "string" && typeof value.expiresAt === "string") {
      return { token: value.token, email: value.email, expiresAt: value.expiresAt }
    }
  } catch {
    // fall through: a corrupt entry counts as signed out
  }
  return null
}

/** The current session, or null when signed out or expired. Safe to call outside React (e.g. the API client). */
export function readSession(): Session | null {
  if (typeof window === "undefined") return null
  const raw = storedRaw()
  if (raw !== cachedRaw) {
    cachedRaw = raw
    cachedSession = parse(raw)
  }
  return cachedSession && Date.parse(cachedSession.expiresAt) > Date.now() ? cachedSession : null
}

function notify() {
  for (const listener of listeners) listener()
}

// Whether the last session ended because the person chose to (sign out, delete account) rather than expiring. After
// a deliberate sign-out the next person shouldn't be sent back to the previous person's page.
let endedByUser = false

export function sessionEndedByUser(): boolean {
  return endedByUser
}

export function saveSession(session: Session) {
  endedByUser = false
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session))
  } finally {
    notify()
  }
}

export function clearSession({ byUser = false }: { byUser?: boolean } = {}) {
  endedByUser = byUser
  try {
    window.localStorage.removeItem(STORAGE_KEY)
  } finally {
    notify()
  }
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  window.addEventListener("storage", listener) // signing out in another tab signs out here too
  return () => {
    listeners.delete(listener)
    window.removeEventListener("storage", listener)
  }
}

/** The session in a Client Component. Suspends during prerendering; wrap the caller in <Suspense>. */
export function useSession(): Session | null {
  use(browser("The sign-in session is kept in this browser's storage."))
  return useSyncExternalStore(subscribe, readSession, () => null)
}
