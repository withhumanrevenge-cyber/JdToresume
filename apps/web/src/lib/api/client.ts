/**
 * The typed API client. Paths, parameters and response shapes come from the FastAPI OpenAPI schema
 * (packages/api-types, regenerated with `pnpm api-types`), so a backend change that breaks the web app fails the
 * type check instead of the user.
 */
import createClient from "openapi-fetch"

import type { components, paths } from "@tailor/api-types"
import { clearSession, readSession } from "@/lib/session"

export type Schemas = components["schemas"]

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "")

export const api = createClient<paths>({ baseUrl: API_URL })

api.use({
  onRequest({ request }) {
    const session = readSession()
    if (session) request.headers.set("Authorization", `Bearer ${session.token}`)
    return request
  },
  onResponse({ response }) {
    if (response.status === 401) clearSession() // expired or revoked: the session gate sends the user to sign in
  },
})

/** The headers for requests made with plain fetch (the generate stream, file downloads). */
export function authHeaders(): Record<string, string> {
  const session = readSession()
  return session ? { Authorization: `Bearer ${session.token}` } : {}
}

/** An error the API reported on purpose: `{code, message, details}` (server/app/core/errors.py). */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly details?: Record<string, unknown>,
  ) {
    super(message)
    this.name = "ApiError"
  }
}

type ErrorBody = { code?: unknown; message?: unknown; details?: unknown }

export function toApiError(status: number, body: unknown): ApiError {
  const { code, message, details } = (body ?? {}) as ErrorBody
  const detailObject = details && typeof details === "object" ? (details as Record<string, unknown>) : undefined
  if (typeof code === "string" && typeof message === "string") {
    return new ApiError(status, code, message, detailObject)
  }
  if (status === 401) return new ApiError(status, "unauthorized", "Your session ended. Sign in again.")
  if (status >= 500) return new ApiError(status, "server_error", "Something went wrong on our side. Try again in a moment.")
  return new ApiError(status, "http_error", `The request failed (${status}).`)
}

export const NETWORK_ERROR = new ApiError(0, "network_error", "Can't reach the server. Check your connection and try again.")

type Result<T> = { data?: T; error?: unknown; response: Response }

/** Await an openapi-fetch call and return its data, or throw an ApiError the UI can show as is. */
export async function unwrap<T>(request: Promise<Result<T>>): Promise<T> {
  let result: Result<T>
  try {
    result = await request
  } catch {
    throw NETWORK_ERROR
  }
  if (!result.response.ok) throw toApiError(result.response.status, result.error)
  return result.data as T
}

/** A message for any thrown value, for toasts and inline errors. */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  return "Something went wrong. Try again."
}
