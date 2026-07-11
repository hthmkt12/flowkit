import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

describe('dashboard Vite config security floors', () => {
  it('does not export a bearer subprotocol helper', async () => {
    const mod = await import('./vite.config')
    expect((mod as Record<string, unknown>).dashboardProxyBearerSubprotocol).toBeUndefined()
  })

  it('vite.config source rejects bearer env and binds loopback', () => {
    const source = readFileSync(resolve(__dirname, 'vite.config.ts'), 'utf8')
    expect(source).toContain('ZOOPOST_CLOUD_DEV_BEARER_TOKEN')
    expect(source).not.toContain('dashboardProxyBearerSubprotocol')
    expect(source).not.toContain('Authorization')
    expect(source).toContain("host: '127.0.0.1'")
  })
})
