import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { ApiError, api, unwrap } from "@/lib/api/client"

export const scanKey = (jobId: string) => ["scans", jobId] as const

/** My latest scan of this job, or null when it hasn't been scanned yet (a 404 "not_scanned"). */
export function useLatestScan(jobId: string | undefined) {
  return useQuery({
    queryKey: scanKey(jobId ?? ""),
    enabled: Boolean(jobId),
    queryFn: async () => {
      try {
        return await unwrap(api.GET("/v1/scans", { params: { query: { job_id: jobId ?? "" } } }))
      } catch (error) {
        if (error instanceof ApiError && error.code === "not_scanned") return null
        throw error
      }
    },
  })
}

/** Scan the job against my current profile. Free: no pack is spent. */
export function useRunScan(jobId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => unwrap(api.POST("/v1/scans", { body: { job_id: jobId } })),
    onSuccess: (scan) => queryClient.setQueryData(scanKey(jobId), scan),
  })
}
