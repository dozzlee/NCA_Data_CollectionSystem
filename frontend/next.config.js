/** @type {import('next').NextConfig} */
const nextConfig = {
  // Windows/OneDrive may block the symlinks used by standalone tracing.
  // Deployments keep standalone output; local verification can opt out.
  output: process.env.NEXT_DISABLE_STANDALONE === "1" ? undefined : "standalone",
  skipTrailingSlashRedirect: true,
  async rewrites() {
    // Proxy /api/* to Django server-side so the browser never needs
    // direct access to port 8000. Works for local dev and single-port
    // deployments like Hugging Face Spaces.
    const djangoUrl = process.env.DJANGO_INTERNAL_URL ?? "http://127.0.0.1:8001";
    return [
      {
        source: "/api/:path*/",
        destination: `${djangoUrl}/api/:path*/`,
      },
      {
        source: "/api/:path*",
        destination: `${djangoUrl}/api/:path*/`,
      },
    ];
  },
};

module.exports = nextConfig;
