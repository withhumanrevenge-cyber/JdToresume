import { describe, expect, it } from "vitest"

import { safeNextPath } from "@/features/auth/api"
import { filenameFromDisposition } from "@/lib/api/files"
import { fillPlaceholders } from "@/lib/placeholders"

describe("filenameFromDisposition", () => {
  it("prefers the UTF-8 name and falls back to the plain one", () => {
    const header = `attachment; filename="Jose-Garcia-Resume.pdf"; filename*=UTF-8''Jos%C3%A9-Garc%C3%ADa-Resume.pdf`
    expect(filenameFromDisposition(header, "x.pdf")).toBe("José-García-Resume.pdf")
    expect(filenameFromDisposition('attachment; filename="Resume.pdf"', "x.pdf")).toBe("Resume.pdf")
    expect(filenameFromDisposition(null, "x.pdf")).toBe("x.pdf")
  })
})

describe("fillPlaceholders", () => {
  const contact = { full_name: "Jordan Rivera", email: "j@example.com", phone: null, city: "Austin, TX", links: ["linkedin.com/in/jr", "github.com/jr"] }

  it("restores the contact details the AI never saw", () => {
    expect(fillPlaceholders("{{FULL_NAME}} · {{LINK_1}} · {{CITY}}", contact)).toBe("Jordan Rivera · github.com/jr · Austin, TX")
  })

  it("leaves unknown placeholders alone and empties missing optional ones", () => {
    expect(fillPlaceholders("{{PHONE}}|{{LINK_7}}", contact)).toBe("|{{LINK_7}}")
    expect(fillPlaceholders("{{FULL_NAME}}", null)).toBe("{{FULL_NAME}}")
  })
})

describe("safeNextPath", () => {
  it("only allows same-site paths after sign-in", () => {
    expect(safeNextPath("/applications/123")).toBe("/applications/123")
    for (const unsafe of ["https://evil.example", "//evil.example", "/\\evil.example", null]) {
      expect(safeNextPath(unsafe)).toBe("/applications")
    }
  })
})
