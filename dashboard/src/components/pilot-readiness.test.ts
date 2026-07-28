import { describe, expect, it } from 'vitest'
import { EVIDENCE_FRESHNESS_MS, isEvidenceFresh } from './pilot-readiness'

const now = Date.parse('2026-07-25T12:00:00.000Z')

describe('isEvidenceFresh', () => {
  it('accepts activity evidence created within the freshness window', () => {
    expect(isEvidenceFresh([
      { id: 'event-1', type: 'job.evidence', severity: 'info', message: 'ready', target_id: null, created_at: '2026-07-25T09:00:01.000Z' },
    ], now)).toBe(true)
  })

  it('rejects stale or timestamp-less activity evidence', () => {
    expect(isEvidenceFresh([
      { id: 'event-1', type: 'job.evidence', severity: 'info', message: 'old', target_id: null, created_at: '2026-07-25T07:59:59.000Z' },
    ], now)).toBe(false)
    expect(isEvidenceFresh([
      { id: 'event-2', type: 'job.evidence', severity: 'info', message: 'unknown', target_id: null, created_at: null },
    ], now)).toBe(false)
  })

  it('reports unknown when the performance request did not return', () => {
    expect(isEvidenceFresh(undefined, now)).toBeNull()
    expect(isEvidenceFresh([], now + EVIDENCE_FRESHNESS_MS)).toBe(false)
  })
})
