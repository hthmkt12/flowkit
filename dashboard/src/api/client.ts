const BASE = ''  // same origin, proxied by Vite in dev
const TOKEN_STORAGE_KEY = 'zoopostBearerToken'

export function getZooPostBearerToken(): string {
  if (typeof window === 'undefined') return ''
  return window.localStorage.getItem(TOKEN_STORAGE_KEY)?.trim() ?? ''
}

export async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getZooPostBearerToken()
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
  })
  if (!res.ok) {
    const err = await res.text().catch(() => res.statusText)
    throw new Error(`API ${res.status}: ${err}`)
  }
  if (res.status === 204) return undefined as T

  if (typeof res.text !== 'function') return res.json()

  const text = await res.text()
  if (!text.trim()) return undefined as T

  return JSON.parse(text) as T
}

export async function postAPI<T>(path: string, body?: unknown): Promise<T> {
  return fetchAPI<T>(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined })
}

export async function patchAPI<T>(path: string, body?: unknown): Promise<T> {
  return fetchAPI<T>(path, { method: 'PATCH', body: body ? JSON.stringify(body) : undefined })
}

export async function deleteAPI<T>(path: string): Promise<T> {
  return fetchAPI<T>(path, { method: 'DELETE' })
}
