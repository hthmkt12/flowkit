import { describe, expect, it } from 'vitest'
import { dashboardProxyBearerSubprotocol } from './vite.config'

describe('dashboard Vite proxy config helpers', () => {
  it('encodes dev proxy WebSocket bearer tokens as browser-safe subprotocols', () => {
    const protocol = dashboardProxyBearerSubprotocol('abc+123/==')

    expect(protocol).toBe('bearer.b64.YWJjKzEyMy89PQ')
    expect(protocol).toMatch(/^[A-Za-z0-9._-]+$/u)
  })
})
