import { useMutation, useQuery, type QueryClient } from "@tanstack/react-query"

import { api, unwrap } from "@/lib/api/client"
import { clearSession, saveSession } from "@/lib/session"

export const meKey = ["me"] as const

/** Development sign-in: any email, no password (the route only exists while the API runs with AUTH_MODE=dev). */
export function useDevSignIn() {
  return useMutation({
    mutationFn: (email: string) => unwrap(api.POST("/v1/dev/sign-in", { body: { email } })),
    onSuccess: (signedIn, email) => saveSession({ token: signedIn.token, email, expiresAt: signedIn.expires_at }),
  })
}

export function useMe() {
  return useQuery({ queryKey: meKey, queryFn: () => unwrap(api.GET("/v1/me")) })
}

/** Forget the session and everything cached for this user. The session gate then shows the sign-in page. */
export function signOut(queryClient: QueryClient) {
  clearSession({ byUser: true })
  queryClient.clear()
}

/** Only same-site paths are allowed after sign-in, so a crafted link can't send people elsewhere. */
export function safeNextPath(next: string | null): string {
  return next && next.startsWith("/") && !next.startsWith("//") && !next.startsWith("/\\") ? next : "/applications"
}
