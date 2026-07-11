import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchAPI } from './client'

describe('fetchAPI', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.unstubAllEnvs()
    window.localStorage.clear()
    window.sessionStorage.clear()
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

  it('never attaches an Authorization header or reads a bearer token', async () => {
    window.localStorage.setItem('zoopostBearerToken', 'should-not-be-used')
    window.sessionStorage.setItem('zoopostBearerToken', 'should-not-be-used')
    const fetchMock = vi.fn(() => Promise.resolve({ ok: true, status: 200, text: () => Promise.resolve('{"ok":true}') } as Response))
    vi.stubGlobal('fetch', fetchMock)

    await fetchAPI<{ ok: boolean }>('/api/data')

    const firstCall = (fetchMock.mock.calls as unknown as Array<[string, RequestInit]>)[0]
    const callInit = firstCall[1]
    const headers = callInit.headers as Record<string, string>
    expect(headers.Authorization).toBeUndefined()
    expect(headers.authorization).toBeUndefined()
  })

  it('preserves caller-supplied non-credential headers', async () => {
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
        'Content-Type': 'application/json',
        'X-Trace-ID': 'trace-1',
      }),
    }))
  })
})
