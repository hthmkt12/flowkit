export interface Project {
  id: string
  tenant_id: string
  name: string
  niche: string | null
  status: 'active' | 'paused' | 'archived'
  safety_policy_id: string | null
  live_enabled: boolean
  dry_run_required: boolean
  default_autopilot_mode: 'draft' | 'assisted' | 'guarded_autopilot' | 'manual_required'
  allowed_target_types: string[]
  kill_switch_enabled: boolean
  metadata: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface TargetRegistry {
  id: string
  tenant_id: string
  project_id: string
  target_type: 'fanpage' | 'profile' | 'group' | 'post' | 'lead'
  platform: string
  social_channel_id: string | null
  label: string
  safe_external_id_hash: string | null
  status: 'active' | 'paused' | 'blocked' | 'stale'
  readiness: 'unknown' | 'ready' | 'offline' | 'checkpoint' | 'logged_out'
  last_seen_at: string | null
  rules: Record<string, unknown>
  metadata: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface AffiliateCampaign {
  id: string
  tenant_id: string
  project_id: string
  created_by: string
  name: string
  offer_name: string | null
  affiliate_network: string | null
  status: 'draft' | 'ready' | 'paused' | 'archived'
  default_caption: Record<string, unknown>
  link_template: Record<string, unknown>
  metadata: Record<string, unknown>
  created_at: string
  updated_at: string
  content_items?: CampaignContentItem[]
}

export interface CampaignContentItem {
  content_item_id: string
  title: string | null
  content_type: string
  rights_status: string
  duplicate_fingerprint: string | null
  sort_order: number
  options: Record<string, unknown>
}

export interface CampaignTargetItem {
  target_registry_id: string
  target_type: string
  platform: string
  label: string
  status: string
  readiness: string
  sort_order: number
  options: Record<string, unknown>
}

export interface PolicyDecision {
  id: string
  tenant_id: string
  project_id: string
  campaign_id: string | null
  publish_job_id: string | null
  publish_job_target_id: string | null
  target_registry_id: string | null
  action_type: string
  risk_tier: 'R0' | 'R1' | 'R2' | 'R3' | 'R4'
  decision: 'allow_auto' | 'require_approval' | 'block'
  reasons: string[]
  input_summary: Record<string, unknown>
  created_by: string
  created_at: string
}

export interface RunEvidence {
  id: string
  tenant_id: string
  project_id: string
  campaign_id: string | null
  publish_job_id: string
  evidence_type: 'dry_run' | 'live_run' | 'policy_preview'
  summary: {
    campaign_id?: string | null
    counts: {
      total: number
      queued: number
      dispatching: number
      posted: number
      failed: number
      cancelled: number
    }
    percent_complete: number
    targets: Array<{
      id: string
      target_registry_id: string | null
      channel_id: string | null
      status: string
      attempts: number
      error_code: string | null
      error_message: string | null
    }>
    decisions?: Record<string, 'allow_auto' | 'require_approval' | 'block'>
  }
  artifact_refs: Array<{
    type: string
    url?: string
    local_path?: string
  }>
  created_at: string
}

export interface PolicyPreviewResult {
  campaign_id: string
  planned_action_count: number
  summary: {
    allow_auto: number
    require_approval: number
    block: number
  }
  planned_actions: Array<{
    content_item_id: string
    target_registry_id: string
    target_label: string
    scheduled_for: string
    action_type: string
    risk_tier: string
    decision: PolicyDecision
    content_sort_order: number
    target_sort_order: number
  }>
}

export interface CampaignDryRunResponse {
  campaign_id: string
  job_count: number
  planned_action_count: number
  jobs: Array<{
    id: string
    tenant_id: string
    project_id: string
    campaign_id: string
    content_item_id: string
    schedule_mode: string
    scheduled_at: string
    status: string
    dry_run: boolean
    autopilot_mode: string
    evidence_required: boolean
    targets: Array<{
      id: string
      target_registry_id: string
      channel_id: string | null
      status: string
      action_type: string
      risk_tier: string
      approval_status: string
      scheduled_for: string
    }>
  }>
}
