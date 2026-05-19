const BASE = ''  // same origin, proxied by Vite in dev
const TOKEN_STORAGE_KEY = 'zoopostBearerToken'

export function getZooPostBearerToken(): string {
  const envToken = import.meta.env.VITE_ZOOPOST_CLOUD_BROWSER_TOKEN
  if (typeof envToken === 'string' && envToken.trim()) return envToken.trim()
  if (typeof window === 'undefined') return ''
  return window.localStorage.getItem(TOKEN_STORAGE_KEY)?.trim() ?? ''
}

export async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getZooPostBearerToken()
  const res = await fetch(`${BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
    ...options,
  })
  if (!res.ok) {
    const err = await res.text().catch(() => res.statusText)
    throw new Error(`API ${res.status}: ${err}`)
  }
  return res.json()
}

export async function postAPI<T>(path: string, body?: unknown): Promise<T> {
  return fetchAPI<T>(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined })
}

export async function deleteAPI<T>(path: string): Promise<T> {
  return fetchAPI<T>(path, { method: 'DELETE' })
}
