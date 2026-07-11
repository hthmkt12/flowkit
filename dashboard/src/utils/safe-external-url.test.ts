import { describe, expect, it } from 'vitest'
import { safeExternalUrl } from './safe-external-url'

describe('safeExternalUrl', () => {
  it('accepts https URLs', () => {
    expect(safeExternalUrl('https://example.com/post/1')).toBe('https://example.com/post/1')
  })

  it('accepts http only to loopback', () => {
    expect(safeExternalUrl('http://127.0.0.1:8100/a.png')).toBe('http://127.0.0.1:8100/a.png')
    expect(safeExternalUrl('http://localhost:3000/a.png')).toBe('http://localhost:3000/a.png')
    expect(safeExternalUrl('http://[::1]:3000/a.png')).toBe('http://[::1]:3000/a.png')
  })

  it('rejects http to non-loopback', () => {
    expect(safeExternalUrl('http://example.com/a.png')).toBeNull()
    expect(safeExternalUrl('http://10.0.0.1/a.png')).toBeNull()
  })

  it('rejects javascript: scheme (inert)', () => {
    expect(safeExternalUrl('javascript:alert(1)')).toBeNull()
  })

  it('rejects data: scheme (inert)', () => {
    expect(safeExternalUrl('data:text/html,<script>alert(1)</script>')).toBeNull()
  })

  it('rejects credentials-in-authority', () => {
    expect(safeExternalUrl('https://user:pass@example.com/a')).toBeNull()
    expect(safeExternalUrl('http://user:pass@127.0.0.1/a')).toBeNull()
  })

  it('handles null/empty/invalid', () => {
    expect(safeExternalUrl(null)).toBeNull()
    expect(safeExternalUrl('')).toBeNull()
    expect(safeExternalUrl('not a url')).toBeNull()
  })
})
