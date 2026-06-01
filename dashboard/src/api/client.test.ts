import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchAPI, getZooPostBearerToken } from './client'

describe('fetchAPI', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.unstubAllEnvs()
  })

  it('returns undefined for HTTP 204 responses without parsing JSON', async () => {
    const text = vi.fn()
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({ ok: true, status: 204, text } as unknown as Response)))

    await expect(fetchAPI<void>('/api/no-content')).resolves.toBeUndefined()
    expect(text).not.toHaveBeenCalled()
  })

  it('returns undefined for empty successful responses', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({ ok: true, status: 200, text: () => Promise.resolve('') } as Response)))

    await expect(fetchAPI<void>('/api/empty')).resolves.toBeUndefined()
  })

  it('parses JSON payloads when a successful response has content', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({ ok: true, status: 200, text: () => Promise.resolve('{"ok":true}') } as Response)))

    await expect(fetchAPI<{ ok: boolean }>('/api/data')).resolves.toEqual({ ok: true })
  })

  it('does not read browser bearer tokens from Vite client env', () => {
    window.localStorage.clear()
    vi.stubEnv('VITE_ZOOPOST_CLOUD_BROWSER_TOKEN', 'bundled-secret')

    expect(getZooPostBearerToken()).toBe('')
  })

  it('preserves bearer auth when callers pass custom headers', async () => {
    window.localStorage.setItem('zoopostBearerToken', 'browser-token')
    const fetchMock = vi.fn(() => Promise.resolve({ ok: true, status: 200, text: () => Promise.resolve('{"ok":true}') } as Response))
    vi.stubGlobal('fetch', fetchMock)

    await fetchAPI<{ ok: boolean }>('/api/custom', {
      method: 'PATCH',
      headers: { 'X-Trace-ID': 'trace-1' },
      body: JSON.stringify({ status: 'ready' }),
    })

    expect(fetchMock).toHaveBeenCalledWith('/api/custom', expect.objectContaining({
      method: 'PATCH',
      body: JSON.stringify({ status: 'ready' }),
      headers: expect.objectContaining({
        Authorization: 'Bearer browser-token',
        'Content-Type': 'application/json',
        'X-Trace-ID': 'trace-1',
      }),
    }))
  })
})
