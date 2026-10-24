import { useMutation, useQueryClient } from "@tanstack/react-query"

import { signOut } from "@/features/auth/api"
import { api, unwrap } from "@/lib/api/client"
import { fetchFile, saveBlob } from "@/lib/api/files"

/** Everything stored about me as one JSON file (DPDP/GDPR right of access). */
export function useExportData() {
  return useMutation({
    mutationFn: async () => {
      const file = await fetchFile("/v1/me/export", "account-export.json")
      saveBlob(file.blob, file.filename)
      return file.filename
    },
  })
}

/** Delete the account and all its data on the server, then forget the session here. */
export function useDeleteAccount() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => unwrap(api.DELETE("/v1/me")),
    onSuccess: () => signOut(queryClient),
  })
}
