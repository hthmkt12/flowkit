import { defineConfig } from 'vitest/config'
import { loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const fbkitTarget = env.VITE_FBKIT_API_URL || 'http://127.0.0.1:8100'
  const zoopostCloudTarget = env.VITE_ZOOPOST_CLOUD_API_URL || 'http://127.0.0.1:8200'
  const zoopostCloudBearerToken = env.ZOOPOST_CLOUD_DEV_BEARER_TOKEN
  const zoopostCloudApiProxy = zoopostCloudBearerToken
    ? { target: zoopostCloudTarget, changeOrigin: true, headers: { Authorization: `Bearer ${zoopostCloudBearerToken}` } }
    : { target: zoopostCloudTarget, changeOrigin: true }
  const zoopostCloudWsProxy = zoopostCloudBearerToken
    ? {
        target: zoopostCloudTarget.replace(/^http/, 'ws'),
        changeOrigin: true,
        ws: true,
        headers: { 'Sec-WebSocket-Protocol': `bearer.${zoopostCloudBearerToken}` },
      }
    : { target: zoopostCloudTarget.replace(/^http/, 'ws'), changeOrigin: true, ws: true }

  return {
    plugins: [react(), tailwindcss()],
    server: {
      port: 5173,
      proxy: {
        '/api/agent-installations': zoopostCloudApiProxy,
        '/api/channels': zoopostCloudApiProxy,
        '/api/content-items': zoopostCloudApiProxy,
        '/api/media-assets': zoopostCloudApiProxy,
        '/api/publish-jobs': zoopostCloudApiProxy,
        '/api/live-arms': zoopostCloudApiProxy,
        '/api/audit-logs': zoopostCloudApiProxy,
        '/api/dashboard': zoopostCloudApiProxy,
        '/agent-gateway': { target: zoopostCloudTarget, changeOrigin: true, ws: true },
        '/ws/dashboard': zoopostCloudWsProxy,
        '/api': { target: fbkitTarget, changeOrigin: true },
        '/ws': { target: fbkitTarget.replace(/^http/, 'ws'), ws: true },
        '/health': { target: fbkitTarget, changeOrigin: true },
      },
    },
    build: { outDir: 'dist' },
    test: {
      environment: 'jsdom',
    },
  }
})
