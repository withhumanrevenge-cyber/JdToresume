import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { ApiError, api, unwrap, type Schemas } from "@/lib/api/client"

export const profileKey = ["profile"] as const
export const contactKey = ["contact"] as const
/** What the last upload found, kept to pre-fill the form when the resume had no usable name or email. */
export const detectedContactKey = ["contact", "detected"] as const

/** A 404 here just means "not created yet", which screens show as an empty state rather than an error. */
async function orNull<T>(request: Promise<T>): Promise<T | null> {
  try {
    return await request
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null
    throw error
  }
}

export function useProfile() {
  return useQuery({ queryKey: profileKey, queryFn: () => orNull(unwrap(api.GET("/v1/profile"))) })
}

export function useContact() {
  return useQuery({ queryKey: contactKey, queryFn: () => orNull(unwrap(api.GET("/v1/profile/contact"))) })
}

export function useUploadResume() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (file: File) =>
      unwrap(
        api.POST("/v1/profile/resume", {
          body: { file: "" }, // the real body is the FormData below; the schema types the file as a string
          bodySerializer: () => {
            const form = new FormData()
            form.append("file", file)
            return form
          },
        }),
      ),
    onSuccess: (result) => {
      queryClient.setQueryData(profileKey, result.profile)
      if (result.contact) queryClient.setQueryData(contactKey, result.contact)
      else queryClient.setQueryData(detectedContactKey, result.detected_contact)
    },
  })
}

export function useSaveContact() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (contact: Schemas["ContactIn"]) => unwrap(api.PUT("/v1/profile/contact", { body: contact })),
    onSuccess: (saved) => queryClient.setQueryData(contactKey, saved),
  })
}
