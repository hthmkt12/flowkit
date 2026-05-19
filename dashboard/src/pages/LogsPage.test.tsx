import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import LogsPage from './LogsPage'

function jsonResponse(body: unknown) {
  return Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response)
}

describe('LogsPage evidence view', () => {
  const sensitiveText = 'secret-token credential-cookie 100004822807900 https://facebook.com/profile'

  beforeEach(() => {
    Object.assign(navigator, { clipboard: { writeText: vi.fn() } })
    vi.stubGlobal('fetch', vi.fn((url: string) => {
      if (url === '/api/dashboard/summary') return jsonResponse({ kpis: { scheduled_posts: 2, published_posts: 1, total_channels: 1, total_reach: 0 }, status_bar: { buffer_api: 'not_configured', imgbb_api: 'not_configured', pancake: 'not_synced' }, scheduled_targets: 2, published_targets: 1, failed_targets: 0, total_channels: 1 })
      if (url === '/api/publish-jobs?limit=8') return jsonResponse([{ id: 'job-12345678', status: 'completed', dry_run: true, created_at: '2026-05-19T09:00:00Z', targets: [{ id: 'target-1', status: 'posted' }] }])
      if (url === '/api/audit-logs?limit=12') return jsonResponse({ items: [{ id: 'audit-1', created_at: '2026-05-19T09:01:00Z', actor_user_id: 'user-a', actor_agent_id: null, action: 'publish_job.created', resource_type: 'publish_job', resource_id: 'job-12345678', data: { dry_run: true } }], limit: 12 })
      if (url === '/api/channels/selector?limit=20') return jsonResponse({ items: [{ id: 'channel-1', platform: 'facebook', channel_type: 'profile', username: null, display_name: 'Local Pilot Profile', connection_status: 'ready', safe_display_id: 'profile-safe', live_guard_enabled: false, is_selectable: false, disabled_reason: 'mvp_live_scope_facebook_fanpage_only', supported_task_types: [] }], limit: 20 })
      if (url === '/api/agent-installations') return jsonResponse([{ id: 'installation-1', name: 'Local Pilot Agent', token_generation: 1, status: 'active', version: null, credential_last_used_at: null, revoked_at: null }])
      if (url === '/api/agent-installations/installation-1/sessions') return jsonResponse([{ id: 'session-1', agent_installation_id: 'installation-1', status: 'online', session_generation: 1, last_sequence: 2, last_heartbeat_at: '2026-05-19T09:02:00Z', capability_names: ['publish-dry-run'], connected_profile_count: 1, has_facebook_profile: true, live_guard_enabled: false, dry_run_ready: true }])
      return Promise.resolve({ ok: false, status: 404, text: () => Promise.resolve(`missing mock ${url} ${sensitiveText}`) } as Response)
    }))
  })

  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it('renders browser-safe demo evidence from Cloud APIs', async () => {
    render(<LogsPage />)

    expect(await screen.findByText('Ready agent sessions')).toBeTruthy()
    expect(screen.getByText('Local Pilot Agent')).toBeTruthy()
    expect(screen.getAllByText('READY').length).toBeGreaterThan(0)
    expect(screen.getByText('job-1234')).toBeTruthy()
    expect(screen.getByText('publish_job.created')).toBeTruthy()
    expect(screen.getByText('dry_run=true')).toBeTruthy()
    expect(screen.getByText('no agent credential in browser')).toBeTruthy()
    expect(screen.getByText('Pilot Summary')).toBeTruthy()
    expect(screen.getByText(/Ready dry-run agent sessions: 1/)).toBeTruthy()
    expect(screen.getByText(/Selectable fanpage channels: 0/)).toBeTruthy()
    expect(screen.getByText('Local Pilot Checklist')).toBeTruthy()
    expect(screen.getByText('.\\scripts\\demo-sales-local-pilot-ready.ps1 -StartPairedFbkit -StopExistingFbkit')).toBeTruthy()
    expect(screen.getByText('Sales Demo Script')).toBeTruthy()
    expect(screen.getByText(/paired to ZooPost Cloud/)).toBeTruthy()
    expect(screen.getByText('Safety boundary visible')).toBeTruthy()
    expect(screen.getByText('Demo readiness')).toBeTruthy()
    expect(screen.getByText('Ready to demo')).toBeTruthy()
    expect(screen.getByText('Dry-run posted')).toBeTruthy()
    expect(screen.getByText('Live actions off')).toBeTruthy()
    expect(screen.getByText('Extension ready')).toBeTruthy()
    expect(screen.getByText('Customer-safe evidence')).toBeTruthy()

    await waitFor(() => {
      expect(screen.queryByText('100004822807900')).toBeNull()
      expect(screen.queryByText('secret-token')).toBeNull()
      expect(screen.queryByText('credential-cookie')).toBeNull()
      expect(screen.queryByText('https://facebook.com/profile')).toBeNull()
    })
  })
})
