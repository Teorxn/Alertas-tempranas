import type { NextConfig } from "next";

const api = process.env.API_UPSTREAM || "http://127.0.0.1:8000";
const produccion = process.env.NODE_ENV === "production";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  async rewrites() {
    // El navegador habla siempre con /api en el mismo origen: no hay problemas
    // de CORS ni de cookies entre puertos distintos.
    return [{ source: "/api/:path*", destination: `${api}/api/:path*` }];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "geolocation=(), microphone=(), camera=()" },
          {
            key: "Content-Security-Policy",
            value: [
              "default-src 'self'",
              "base-uri 'self'",
              "object-src 'none'",
              "frame-ancestors 'none'",
              "form-action 'self'",
              "img-src 'self' data:",
              "style-src 'self' 'unsafe-inline'",
              `script-src 'self'${produccion ? "" : " 'unsafe-inline' 'unsafe-eval'"}`,
              "connect-src 'self'",
            ].join("; "),
          },
        ],
      },
    ];
  },
};

export default nextConfig;
