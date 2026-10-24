import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { api, unwrap } from "@/lib/api/client"

export const applicationsKey = ["applications"] as const
export const applicationKey = (id: string) => ["applications", id] as const
export const jobKey = (id: string) => ["jobs", id] as const

const PAGE_SIZE = 20

/** My applications, newest first, a page at a time (keyset pagination: `before` = the last item's date). */
export function useApplications() {
  return useInfiniteQuery({
    queryKey: applicationsKey,
    queryFn: ({ pageParam }) =>
      unwrap(api.GET("/v1/applications", { params: { query: { limit: PAGE_SIZE, before: pageParam } } })),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_before ?? undefined,
  })
}

export function useApplication(id: string) {
  return useQuery({
    queryKey: applicationKey(id),
    queryFn: () => unwrap(api.GET("/v1/applications/{application_id}", { params: { path: { application_id: id } } })),
  })
}

/** The full job (requirements, keywords), which the match report refers to by id. */
export function useJob(id: string | undefined) {
  return useQuery({
    queryKey: jobKey(id ?? ""),
    queryFn: () => unwrap(api.GET("/v1/jobs/{job_id}", { params: { path: { job_id: id ?? "" } } })),
    enabled: Boolean(id),
    staleTime: Infinity, // a job posting doesn't change once read
  })
}

export type JobSource = { url: string } | { text: string }

/** Read the job (link or pasted text), then start an application for it. Returns the application. */
export function useStartApplication() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (source: JobSource) => {
      const job = await unwrap(api.POST("/v1/jobs", { body: source }))
      queryClient.setQueryData(jobKey(job.id), job)
      return unwrap(api.POST("/v1/applications", { body: { job_id: job.id } }))
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: applicationsKey }),
  })
}
