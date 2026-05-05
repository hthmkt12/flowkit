// ── FBKit Dashboard Types ─────────────────────────────────────

export type TaskStatus = 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED' | 'CANCELLED'
export type AccountStatus = 'ACTIVE' | 'PAUSED' | 'BANNED' | 'LOGGED_OUT'
export type CampaignStatus = 'ACTIVE' | 'PAUSED' | 'COMPLETED' | 'CANCELLED'
export type SpyTargetStatus = 'ACTIVE' | 'PAUSED'

export interface Account {
  id: string
  name: string
  fb_uid: string | null
  email: string | null
  status: AccountStatus
  profile_url: string | null
  avatar_url: string | null
  cookies_valid: number
  last_active: string | null
  daily_posts: number
  daily_messages: number
  daily_likes: number
  daily_comments: number
  daily_friends: number
  daily_reset_at: string | null
  created_at: string
  updated_at: string
}

export interface Task {
  id: string
  account_id: string | null
  task_type: string
  payload: string | null
  ref_id: string | null
  status: TaskStatus
  priority: number
  retry_count: number
  max_retries: number
  scheduled_at: string | null
  started_at: string | null
  completed_at: string | null
  result: string | null
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface TaskStats {
  PENDING?: number
  PROCESSING?: number
  COMPLETED?: number
  FAILED?: number
  CANCELLED?: number
}

export interface SeedCampaign {
  id: string
  name: string
  accounts: string[]
  targets: string[]
  actions: string[]
  status: CampaignStatus
  stats: { total: number; success: number; failed: number }
}

export interface SpyTarget {
  id: string
  page_name: string
  page_id: string
  page_url: string | null
  check_interval: number
  last_checked: string | null
  ads_found: number
  status: SpyTargetStatus
}

export interface SpyAd {
  id: string
  target_id: string
  fb_ad_id: string | null
  page_name: string | null
  ad_text: string | null
  media_url: string | null
  ad_status: string
  first_seen: string
  last_seen: string
}

// WebSocket event
export interface WSEvent {
  type: string
  data: Record<string, unknown>
  timestamp: string
}
