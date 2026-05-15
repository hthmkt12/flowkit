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

export type DashboardConnectorStatus = 'ready' | 'not_configured' | 'not_synced' | 'offline'

export interface DashboardSummary {
  kpis: {
    scheduled_posts: number
    published_posts: number
    total_channels: number
    total_reach: number
  }
  status_bar: {
    buffer_api: DashboardConnectorStatus
    imgbb_api: DashboardConnectorStatus
    pancake: DashboardConnectorStatus
  }
  scheduled_jobs?: number
  scheduled_targets?: number
  published_targets?: number
  failed_targets?: number
  total_channels?: number
  total_reach?: number
}

export interface DashboardPerformance {
  range: '7d' | '30d'
  line_chart: Array<{
    date: string
    scheduled: number
    published: number
    failed: number
  }>
  status_donut: {
    total: number
    segments: Array<{
      status: string
      count: number
      percent: number
    }>
  }
  channel_performance: Array<{
    id: string
    platform: string
    channel_type: string
    display_name: string
    username: string | null
    safe_display_id: string | null
    connection_status: string
    scheduled: number
    published: number
    reach: number
    engagement: number
    success_rate: number
  }>
  upcoming_posts: Array<{
    job_id: string
    target_id: string
    channel_id: string
    channel_name: string
    scheduled_for: string | null
    status: string
    content_preview: string
  }>
  top_content: Array<{
    job_id: string
    content_id: string
    title: string | null
    body_preview: string
    reach: number
    engagement: number
  }>
  activity_log: Array<{
    id: string
    type: string
    severity: string
    message: string
    target_id: string | null
  }>
}

export interface AgentInstallation {
  id: string
  name: string
  token_generation: number
  status: string
  version: string | null
  credential_last_used_at: string | null
  revoked_at: string | null
}

export interface AgentInstallationCreateResponse extends AgentInstallation {
  registration_token: string
  registration_token_expires_at: string
}

export interface AgentSessionReadiness {
  id: string
  agent_installation_id: string
  status: string
  session_generation: number
  last_sequence: number
  last_heartbeat_at: string | null
  capability_names: string[]
  connected_profile_count: number
  has_facebook_profile: boolean
  live_guard_enabled: boolean
  dry_run_ready: boolean
}

export interface SocialChannel {
  id: string
  platform: string
  channel_type: string
  username: string | null
  display_name: string
  connection_status: string
  safe_display_id?: string | null
}

export interface ContentPreviewResult {
  body: string
  syntax_mode: string
  seed: string
}

export interface PublishJobTarget {
  id: string
  status: string
}

export interface PublishJob {
  id: string
  status: string
  dry_run: boolean
  targets: PublishJobTarget[]
}
