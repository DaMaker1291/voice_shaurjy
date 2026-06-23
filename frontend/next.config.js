/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "export",
  images: { unoptimized: true },
  basePath: process.env.BASE_PATH || "/voice_shaurjy",
};

module.exports = nextConfig;
