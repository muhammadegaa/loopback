import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Static export: the app is a single client-rendered page that talks to the API,
  // so we ship it as static files served same-origin by the FastAPI container.
  output: "export",
  images: { unoptimized: true },
};

export default nextConfig;
