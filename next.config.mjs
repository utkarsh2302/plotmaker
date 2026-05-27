/** @type {import('next').NextConfig} */
const nextConfig = {
  // Allow images from any hostname (for Supabase storage URLs)
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "**.supabase.co" },
    ],
  },
};

export default nextConfig;
