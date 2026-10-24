import { describe, expect, it } from "vitest"

import { SseParser } from "./sse"

describe("SseParser", () => {
  it("returns events only once their blank line has arrived, across chunk boundaries", () => {
    const parser = new SseParser()
    expect(parser.push('event: run\ndata: {"run_id":')).toEqual([])
    expect(parser.push('"r1"}\n\nevent: resu')).toEqual([{ event: "run", data: '{"run_id":"r1"}' }])
    expect(parser.push('me\ndata: {}\n\n')).toEqual([{ event: "resume", data: "{}" }])
  })

  it("skips keep-alive comments and handles \\r\\n line endings", () => {
    const parser = new SseParser()
    expect(parser.push(": keep-alive\r\n\r\nevent: done\r\ndata: {}\r\n\r\n")).toEqual([{ event: "done", data: "{}" }])
  })

  it("joins multi-line data and defaults the event name to message", () => {
    const parser = new SseParser()
    expect(parser.push("data: line one\ndata: line two\n\n")).toEqual([{ event: "message", data: "line one\nline two" }])
  })
})
