import { defineConfig } from "vitest/config"

// Unit tests for logic that doesn't need a browser (stream parsing, file names, text helpers).
export default defineConfig({
  resolve: { tsconfigPaths: true }, // the @/* imports from tsconfig.json
  test: { include: ["src/**/*.test.ts"] },
})
