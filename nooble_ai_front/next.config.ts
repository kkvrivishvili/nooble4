/** @type {import('next').NextConfig} */
import type { Configuration as WebpackConfig } from 'webpack';

const nextConfig = {
  experimental: {
    optimizePackageImports: ['@radix-ui/react-icons', 'lucide-react'],
    serverActions: {
      bodySizeLimit: '2mb',
      allowedOrigins: ['localhost:3000']
    }
  },

  eslint: {
    ignoreDuringBuilds: true,
  },

  typescript: {
    ignoreBuildErrors: true,
  },

  output: 'standalone',
  poweredByHeader: false,
  reactStrictMode: false,

  webpack: (config: WebpackConfig) => {
    config.watchOptions = {
      poll: 1000,
      aggregateTimeout: 300,
    };

    config.experiments = {
      ...config.experiments,
      topLevelAwait: true,
    };

    config.resolve = {
      ...config.resolve,
      fallback: {
        ...config.resolve?.fallback,
        "next-flight-client-entry-loader": "next/dist/build/webpack/loaders/next-flight-client-entry-loader",
      },
    };

    return config;
  },

  transpilePackages: [
    '@radix-ui/react-slot',
    '@radix-ui/react-alert-dialog',
    '@radix-ui/react-avatar',
    '@radix-ui/react-checkbox',
    '@radix-ui/react-dialog',
    '@radix-ui/react-dropdown-menu',
    '@radix-ui/react-label',
    '@radix-ui/react-progress',
    '@radix-ui/react-select',
    '@radix-ui/react-switch',
    '@radix-ui/react-tabs',
    '@radix-ui/react-tooltip',
    'lucide-react',
    'next/dist/compiled/react-server-dom-webpack/client',
    '@supabase/ssr'
  ],

  onDemandEntries: {
    maxInactiveAge: 60 * 1000,
    pagesBufferLength: 5,
  },

  images: {
    domains: ['localhost'],
  },
} satisfies import('next').NextConfig;

export default nextConfig;
