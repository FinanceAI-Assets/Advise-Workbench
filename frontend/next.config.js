/** @type {import('next').NextConfig} */
const apiTarget = process.env.API_PROXY_TARGET || "http://127.0.0.1:8000";

const nextConfig = {
  experimental: {
    // Backend LLM calls can exceed the default ~30s proxy timeout. Allow up to 2 minutes.
    proxyTimeout: 120000,
    // Library uploads go through the /api rewrite: up to 10 sources of 25 MB each (MAX_FILES_PER_UPLOAD,
    // MAX_SOURCE_BYTES) plus multipart overhead. The 10 MB default truncates the body and the upload hangs.
    proxyClientMaxBodySize: "260mb",
  },
  // When the browser uses same-origin `/api/*` (NEXT_PUBLIC_API_URL=same-origin), forward to FastAPI.
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${apiTarget.replace(/\/$/, "")}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
