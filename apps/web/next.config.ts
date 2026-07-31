import type { NextConfig } from "next";

import { withSerwist } from "@serwist/turbopack";
import createNextIntlPlugin from "next-intl/plugin";
import { env } from "./src/config/env";

const withNextIntl = createNextIntlPlugin("./src/lib/i18n/request.ts");

const isDev = env.NEXT_PUBLIC_ENABLE_DEVTOOLS === "true";

const securityHeaders = [
  {
    key: "X-DNS-Prefetch-Control",
    value: "on",
  },
  {
    key: "Strict-Transport-Security",
    value: "max-age=63072000; includeSubDomains; preload",
  },
  {
    key: "X-Content-Type-Options",
    value: "nosniff",
  },
  {
    key: "X-Frame-Options",
    value: "DENY",
  },
  {
    key: "X-XSS-Protection",
    value: "1; mode=block",
  },
  {
    key: "Referrer-Policy",
    value: "strict-origin-when-cross-origin",
  },
];

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  reactStrictMode: true,
  reactCompiler: true,
  // Next 16 blocks /_next/* from non-allowed hosts. Browsers often use 127.0.0.1
  // while the dev server advertises localhost — that breaks client hydration
  // (navbar / form clicks appear dead).
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  devIndicators: isDev ? undefined : false,
  images: {
    formats: ["image/avif", "image/webp"],
  },
  logging: isDev
    ? {
        fetches: {
          fullUrl: true,
        },
      }
    : undefined,
  typescript: {
    ignoreBuildErrors: true,
  },
  experimental: {
    typedEnv: true,
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: securityHeaders,
      },
    ];
  },
};

export default withSerwist(withNextIntl(nextConfig));
