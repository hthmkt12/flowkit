import type { DashboardPerformance } from '../types'

export const EVIDENCE_FRESHNESS_MS = 4 * 60 * 60 * 1000

export function isEvidenceFresh(
  activityLog: DashboardPerformance['activity_log'] | undefined,
  now = Date.now(),
): boolean | null {
  if (!activityLog) return null

  const newestTimestamp = activityLog.reduce<number | null>((newest, event) => {
    if (!event.created_at) return newest
    const parsed = Date.parse(event.created_at)
    if (Number.isNaN(parsed)) return newest
    return newest === null || parsed > newest ? parsed : newest
  }, null)

  if (newestTimestamp === null || newestTimestamp > now) return false
  return now - newestTimestamp <= EVIDENCE_FRESHNESS_MS
}
