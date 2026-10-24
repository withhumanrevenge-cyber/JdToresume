/**
 * Generation runs, one per application, kept outside React.
 *
 * POST /v1/applications/{id}/generate answers with a stream of events: `run`, then `match_report`, then
 * `resume`, `cover_letter` and `outreach` in whichever order they finish, then `done` or `error`. Each piece is
 * shown the moment it arrives. The run lives here rather than in a component so moving to another page doesn't
 * cut the stream (that would cancel the run on the server); coming back shows where it got to.
 */
import type { QueryClient } from "@tanstack/react-query"

import { applicationKey, applicationsKey } from "@/features/applications/api"
import { planKey } from "@/features/billing/api"
import { SseParser } from "@/features/generate/lib/sse"
import { API_URL, ApiError, NETWORK_ERROR, authHeaders, toApiError, type Schemas } from "@/lib/api/client"

export type Mode = "deep" | "quick"
export type PieceKind = "match_report" | "resume" | "cover_letter" | "outreach"
export const PIECE_KINDS: PieceKind[] = ["match_report", "resume", "cover_letter", "outreach"]

export type Pieces = {
  match_report?: Schemas["MatchReport"]
  resume?: Schemas["ResumeOutcome"]
  cover_letter?: Schemas["CoverLetterOutcome"]
  outreach?: Schemas["OutreachOutcome"]
}

export type RunError = { code: string; message: string; details?: Record<string, unknown> }

export type GenerationState = {
  status: "idle" | "starting" | "streaming" | "done" | "failed"
  runId: string | null
  mode: Mode | null
  pieces: Pieces
  lastPiece: PieceKind | null // the piece that arrived most recently, for screen-reader announcements
  error: RunError | null
  startedAt: number | null
}

const IDLE: GenerationState = {
  status: "idle", runId: null, mode: null, pieces: {}, lastPiece: null, error: null, startedAt: null,
}

export class GenerationRun {
  private state: GenerationState = IDLE
  private readonly listeners = new Set<() => void>()

  constructor(private readonly applicationId: string) {}

  subscribe = (listener: () => void) => {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  getSnapshot = () => this.state

  get active() {
    return this.state.status === "starting" || this.state.status === "streaming"
  }

  private update(patch: Partial<GenerationState>) {
    this.state = { ...this.state, ...patch }
    for (const listener of this.listeners) listener()
  }

  /** Start a run. `mode` undefined lets the plan choose. Never throws: problems end up in `state.error`. */
  async start(mode: Mode | undefined, queryClient: QueryClient) {
    if (this.active) return
    this.update({ ...IDLE, status: "starting", startedAt: Date.now() })
    try {
      await this.stream(mode)
    } finally {
      // Whatever happened, the saved pack, the list and the remaining packs may have changed.
      void queryClient.invalidateQueries({ queryKey: applicationKey(this.applicationId) })
      void queryClient.invalidateQueries({ queryKey: applicationsKey, exact: true })
      void queryClient.invalidateQueries({ queryKey: planKey })
    }
  }

  private async stream(mode: Mode | undefined) {
    const query = mode ? `?mode=${mode}` : ""
    let response: Response
    try {
      response = await fetch(`${API_URL}/v1/applications/${this.applicationId}/generate${query}`, {
        method: "POST",
        headers: { ...authHeaders(), Accept: "text/event-stream" },
      })
    } catch {
      return this.fail(NETWORK_ERROR)
    }
    if (!response.ok || !response.body) {
      // Refusals arrive before the stream starts, as ordinary JSON: no packs left, no profile, already running.
      return this.fail(toApiError(response.status, await response.json().catch(() => null)))
    }

    const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
    const parser = new SseParser()
    try {
      for (;;) {
        const { value, done } = await reader.read()
        if (done) break
        for (const event of parser.push(value)) this.handle(event.event, JSON.parse(event.data))
      }
    } catch {
      if (this.active) this.fail(new ApiError(0, "connection_lost", "The connection dropped. Finished pieces are saved; reload to see them."))
      return
    }
    if (this.active) {
      this.fail(new ApiError(0, "connection_lost", "The stream ended early. Finished pieces are saved; reload to see them."))
    }
  }

  private handle(event: string, data: Record<string, unknown>) {
    if (event === "run") {
      this.update({ status: "streaming", runId: String(data.run_id), mode: data.mode as Mode })
    } else if ((PIECE_KINDS as string[]).includes(event)) {
      this.update({ pieces: { ...this.state.pieces, [event]: data }, lastPiece: event as PieceKind })
    } else if (event === "done") {
      this.update({ status: "done" })
    } else if (event === "error") {
      this.update({ status: "failed", error: { code: String(data.code), message: String(data.message) } })
    }
  }

  private fail(error: ApiError) {
    this.update({ status: "failed", error: { code: error.code, message: error.message, details: error.details } })
  }
}

const runs = new Map<string, GenerationRun>()

export function generationRun(applicationId: string): GenerationRun {
  let run = runs.get(applicationId)
  if (!run) {
    run = new GenerationRun(applicationId)
    runs.set(applicationId, run)
  }
  return run
}
