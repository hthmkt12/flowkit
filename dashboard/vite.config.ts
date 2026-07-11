import { defineConfig } from 'vitest/config'
import { loadEnv, type ViteDevServer, type Connect } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

/**
 * Vite config supports LOCAL-DEV ONLY.
 *
 * Local-dev binds to loopback (127.0.0.1), rejects non-loopback Host /
 * forwarded-host headers, and proxies only the minimum named Cloud
 * prefixes plus the local FBKit API/WS for development. No Cloud bearer
 * token is read or injected by this config — the browser must never
 * hold a Cloud bearer, and public mode must not expose dynamic APIs.
 *
 * Public-static mode is served by a separate static file server (see
 * scripts/demo-sales-local-pilot-tunnel-*.ps1) that serves dist/ only
 * with no Vite dev server and no API/WS proxy.
 */

const LOOPBACK = new Set(['127.0.0.1', 'localhost', '::1'])

function isLoopbackHost(host: string | undefined): boolean {
  if (!host) return false
  // Strip port.
  const bare = host.split(':')[0].toLowerCase()
  return LOOPBACK.has(bare)
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const fbkitTarget = env.VITE_FBKIT_API_URL || 'http://127.0.0.1:8100'
  const zoopostCloudTarget = env.VITE_ZOOPOST_CLOUD_API_URL || 'http://127.0.0.1:8200'
  const allowedHosts = (env.VITE_DASHBOARD_ALLOWED_HOSTS || '')
    .split(',')
    .map(host => host.trim())
    .filter(Boolean)

  // Security floors: reject any bearer-token env that would otherwise be
  // injected into proxied Cloud requests or WebSocket subprotocols.
  if (env.ZOOPOST_CLOUD_DEV_BEARER_TOKEN) {
    throw new Error(
      'ZOOPOST_CLOUD_DEV_BEARER_TOKEN must not be set for the dashboard. ' +
      'The browser must never hold a Cloud bearer; local-dev is loopback-only.'
    )
  }

  // Local-dev upstreams must themselves be loopback.
  for (const target of [fbkitTarget, zoopostCloudTarget]) {
    const host = target.replace(/^https?:\/\//, '').split(':')[0].toLowerCase()
    if (!LOOPBACK.has(host)) {
      throw new Error(
        `Local-dev upstream must be loopback, got ${target}. ` +
        'Public/non-loopback upstreams are not permitted by this config.'
      )
    }
  }

  const zoopostCloudApiProxy = { target: zoopostCloudTarget, changeOrigin: true }

  return {
    plugins: [react(), tailwindcss()],
    server: {
      host: '127.0.0.1',
      port: 5173,
      allowedHosts: allowedHosts.length ? allowedHosts : undefined,
      // Reject any non-loopback Host header in local-dev.
      configureServer(server: ViteDevServer) {
        server.middlewares.use((req: Connect.IncomingMessage, res: { statusCode: number; end: (m: string) => void }, next: () => void) => {
          const host = (req.headers.host as string | undefined)
            || (req.headers['forwarded-host'] as string | undefined)
          if (!isLoopbackHost(host)) {
            res.statusCode = 421
            res.end('Misdirected: local-dev dashboard is loopback-only')
            return
          }
          next()
        })
      },
      proxy: {
        // Named minimum Cloud prefixes only.
        '/api/agent-installations': zoopostCloudApiProxy,
        '/api/projects': zoopostCloudApiProxy,
        '/api/channels': zoopostCloudApiProxy,
        '/api/content-items': zoopostCloudApiProxy,
        '/api/media-assets': zoopostCloudApiProxy,
        '/api/publish-jobs': zoopostCloudApiProxy,
        '/api/audit-logs': zoopostCloudApiProxy,
        '/api/dashboard': zoopostCloudApiProxy,
        '/agent-gateway': { target: zoopostCloudTarget, changeOrigin: true, ws: true },
        '/ws/dashboard': { target: zoopostCloudTarget.replace(/^http/, 'ws'), changeOrigin: true, ws: true },
        // Local FBKit API/WS for development (loopback only).
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
