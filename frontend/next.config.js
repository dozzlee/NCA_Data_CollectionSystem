/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  async rewrites() {
    // Proxy /api/* to Django server-side so the browser never needs
    // direct access to port 8000. Works for local dev and single-port
    // deployments like Hugging Face Spaces.
    const djangoUrl = process.env.DJANGO_INTERNAL_URL ?? "http://localhost:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${djangoUrl}/api/:path*/`,
      },
    ];
  },
};

module.exports = nextConfig;
