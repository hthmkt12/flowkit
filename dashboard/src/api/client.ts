const BASE = ''  // same origin, proxied by Vite in dev

/**
 * Public-static / local-dev API client.
 *
 * The dashboard no longer stores or attaches a Cloud bearer token. The
 * browser must never hold long-lived bearer credentials (XSS-readable
 * client storage / JS globals). The public-static UI is anonymous and
 * reads no protected Cloud data. Local-dev relies on loopback-only
 * proxying configured in vite.config.ts. Any future authenticated
 * dashboard must use short-lived HttpOnly/Secure/SameSite server
 * sessions designed in a separate plan — not a browser bearer contract.
 */
export async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
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
