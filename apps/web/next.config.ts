import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  experimental: {
    instantInsights: {
      // Signed-in pages render only in the browser (the dev session lives in browser storage), so there is no
      // server shell to check and the default "validate every page" mode flags the session gate on every route.
      // Only segments that export `instant` are checked. Revisit when Better Auth moves the session into a cookie
      // the server can read (ARCHITECTURE §12).
      validationLevel: "manual-warning",
    },
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
