/** @type {import("next").NextConfig} */
const nextConfig = {
  output: process.env.NEXT_STANDALONE === "false" ? undefined : "standalone",
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
