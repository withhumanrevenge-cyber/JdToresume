"use client"

import { useCallback, useSyncExternalStore } from "react"
import { useQueryClient } from "@tanstack/react-query"

import { generationRun, type Mode } from "@/features/generate/generation-runs"

/** The generation run for one application: its live state, and `start(mode)` (frontend-standards §Streaming). */
export function useGenerationStream(applicationId: string) {
  const run = generationRun(applicationId)
  const state = useSyncExternalStore(run.subscribe, run.getSnapshot, run.getSnapshot)
  const queryClient = useQueryClient()
  const start = useCallback((mode?: Mode) => run.start(mode, queryClient), [run, queryClient])
  const active = state.status === "starting" || state.status === "streaming"
  return { ...state, active, start }
}
