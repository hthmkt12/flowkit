/**
 * Shared URL sanitizer for backend-controlled links/images.
 *
 * Policy:
 * - HTTPS always allowed (to any host).
 * - HTTP allowed only to loopback (127.0.0.1 / localhost / ::1) for
 *   local-dev artifact preview.
 * - javascript:, data:, file: and other non-http(s) schemes are inert
 *   (return null so callers render text without a clickable anchor).
 * - URLs containing user info (credentials in authority) are rejected.
 *
 * An explicit approved-artifact-host allowlist may further restrict
 * non-loopback hosts in the future; today HTTPS + no-credentials is the
 * floor.
 */

const LOOPBACK = new Set(['127.0.0.1', 'localhost', '::1', '[::1]'])

export function safeExternalUrl(url: string | null | undefined): string | null {
  if (!url) return null
  let parsed: URL
  try {
    parsed = new URL(url)
  } catch {
    return null
  }
  // Reject credentials-in-authority.
  if (parsed.username || parsed.password) return null
  if (parsed.protocol === 'https:') return url
  if (parsed.protocol === 'http:') {
    const host = parsed.hostname.toLowerCase()
    if (LOOPBACK.has(host)) return url
    return null
  }
  // Non-http(s) schemes (javascript:, data:, file:) are inert.
  return null
}
