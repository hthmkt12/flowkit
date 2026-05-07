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
  notes: string | null
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

export interface ExtensionSession {
  fb_uid: string | null
  logged_in: boolean
  extension_live_actions_enabled?: boolean | null
  profile_id?: string | null
  profile_name?: string | null
  uptime_s: number
  last_seen_age_s?: number
  stale?: boolean
  health?: 'online' | 'stale'
}

export interface AgentStatus {
  extension: {
    connected: boolean
    session_count: number
    sessions?: ExtensionSession[]
    total_connects: number
    total_disconnects: number
  }
  safety_gate: {
    live_actions_enabled: boolean
    dry_run_default: boolean
    approval_required: boolean
    api_auth_enabled?: boolean
    ws_auth_enabled?: boolean
    live_auth_ready?: boolean
    active_live_arms?: unknown[]
  }
}

// WebSocket event
export interface WSEvent {
  type: string
  data: Record<string, unknown>
  timestamp: string
}
