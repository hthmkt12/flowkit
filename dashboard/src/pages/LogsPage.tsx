import { useCallback, useEffect, useMemo, useState } from 'react'
import type { CSSProperties, ReactNode } from 'react'
import { CheckCircle2, ClipboardList, FileText, Radio, RefreshCw, ShieldCheck, Wifi } from 'lucide-react'
import { fetchAPI } from '../api/client'
import { LocalPilotChecklist } from '../components/local-pilot-checklist'
import { LocalPilotDemoScript } from '../components/local-pilot-demo-script'
import { LocalPilotDemoReadinessStrip } from '../components/local-pilot-demo-readiness-strip'
import { LocalPilotEvidenceSummary } from '../components/local-pilot-evidence-summary'
import type { AgentInstallation, AgentSessionReadiness, AuditLogResponse, ChannelSelectorResponse, DashboardSummary, PublishJob } from '../types'

type EvidenceState = {
  summary: DashboardSummary | null
  jobs: PublishJob[]
  audit: AuditLogResponse | null
  channels: ChannelSelectorResponse | null
  installations: AgentInstallation[]
  sessions: Record<string, AgentSessionReadiness[]>
}

const emptyState: EvidenceState = { summary: null, jobs: [], audit: null, channels: null, installations: [], sessions: {} }

export default function LogsPage() {
  const [state, setState] = useState<EvidenceState>(emptyState)
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [summary, jobs, audit, channels, installations] = await Promise.all([
        fetchAPI<DashboardSummary>('/api/dashboard/summary'),
        fetchAPI<PublishJob[]>('/api/publish-jobs?limit=8'),
        fetchAPI<AuditLogResponse>('/api/audit-logs?limit=12'),
        fetchAPI<ChannelSelectorResponse>('/api/channels/selector?limit=20'),
        fetchAPI<AgentInstallation[]>('/api/agent-installations'),
      ])
      const sessionPairs = await Promise.all(installations.map(async item => [
        item.id,
        await fetchAPI<AgentSessionReadiness[]>(`/api/agent-installations/${item.id}/sessions`),
      ] as const))
      setState({ summary, jobs, audit, channels, installations, sessions: Object.fromEntries(sessionPairs) })
      setMessage(null)
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Khong tai duoc evidence log.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const readySessions = useMemo(() => Object.values(state.sessions).flat().filter(session => session.dry_run_ready), [state.sessions])
  const completedDryRuns = state.jobs.filter(job => job.dry_run && job.status === 'completed').length
  const failedTargets = state.summary?.failed_targets ?? 0
  const selectableChannels = state.channels?.items.filter(channel => channel.is_selectable).length ?? 0

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap' }}>
        <div>
          <div style={{ fontSize: '22px', fontWeight: 850 }}>Evidence Log</div>
          <div style={{ fontSize: '12px', color: 'var(--muted)' }}>Browser-safe proof for the local dry-run pilot: readiness, jobs, audit trail, and safety boundary.</div>
        </div>
        <button type="button" onClick={load} disabled={loading} style={buttonStyle('#2563eb')}>
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {message && <div style={noticeStyle('#d97706')}>{message}</div>}

      <LocalPilotDemoReadinessStrip
        readySessions={readySessions.length}
        completedDryRuns={completedDryRuns}
      />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: '12px' }}>
        <MetricCard icon={<Wifi size={17} />} label="Ready agent sessions" value={readySessions.length} tone="#16a34a" />
        <MetricCard icon={<CheckCircle2 size={17} />} label="Completed dry-runs" value={completedDryRuns} tone="#2563eb" />
        <MetricCard icon={<ClipboardList size={17} />} label="Audit records shown" value={state.audit?.items.length ?? 0} tone="#7c3aed" />
        <MetricCard icon={<ShieldCheck size={17} />} label="Failed targets" value={failedTargets} tone={failedTargets ? '#dc2626' : '#16a34a'} />
      </div>

      <LocalPilotEvidenceSummary
        readySessions={readySessions.length}
        completedDryRuns={completedDryRuns}
        failedTargets={failedTargets}
        auditRecords={state.audit?.items.length ?? 0}
        selectableChannels={selectableChannels}
      />

      <section style={panelStyle()}>
        <SectionTitle icon={<ShieldCheck size={16} />} title="Safety Boundary" />
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '10px' }}>
          {['dry_run=true only', 'no live approval', 'no agent credential in browser', 'no cookies or raw Facebook IDs'].map(item => (
            <div key={item} style={chipStyle('#16a34a')}>{item}</div>
          ))}
        </div>
      </section>

      <LocalPilotChecklist />
      <LocalPilotDemoScript />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '14px', alignItems: 'start' }}>
        <section style={panelStyle()}>
          <SectionTitle icon={<Radio size={16} />} title="Agent Readiness" />
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {state.installations.flatMap(installation => {
              const sessions = state.sessions[installation.id] ?? []
              if (sessions.length === 0) return [<EmptyRow key={installation.id} title={installation.name} meta="No session reported" />]
              return sessions.map(session => (
                <div key={session.id} style={rowStyle()}>
                  <div>
                    <div style={{ fontWeight: 850 }}>{installation.name}</div>
                    <div style={mutedStyle()}>{session.capability_names.join(', ') || 'no capability'} - profiles {session.connected_profile_count}</div>
                  </div>
                  <StatusPill ok={session.dry_run_ready} label={session.dry_run_ready ? 'READY' : session.status.toUpperCase()} />
                </div>
              ))
            })}
            {!loading && state.installations.length === 0 && <EmptyRow title="No agent installation" meta="Create one from Connect Agent" />}
          </div>
        </section>

        <section style={panelStyle()}>
          <SectionTitle icon={<FileText size={16} />} title="Recent Dry-Run Jobs" />
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {state.jobs.filter(job => job.dry_run).map(job => {
              const posted = job.targets.filter(target => target.status === 'posted').length
              const failed = job.targets.filter(target => target.status === 'failed').length
              return (
                <div key={job.id} style={rowStyle()}>
                  <div>
                    <div style={{ fontWeight: 850 }}>{job.id.slice(0, 8)}</div>
                    <div style={mutedStyle()}>{formatTime(job.created_at)} - {job.targets.length} target(s)</div>
                  </div>
                  <div style={{ textAlign: 'right', fontSize: '11px' }}>
                    <div style={{ fontWeight: 850, color: job.status === 'completed' ? '#16a34a' : '#d97706' }}>{job.status}</div>
                    <div style={mutedStyle()}>{posted} posted - {failed} failed</div>
                  </div>
                </div>
              )
            })}
            {!loading && state.jobs.filter(job => job.dry_run).length === 0 && <EmptyRow title="No dry-run jobs" meta="Run the local pilot readiness gate" />}
          </div>
        </section>
      </div>

      <section style={panelStyle()}>
        <SectionTitle icon={<ClipboardList size={16} />} title="Recent Audit Evidence" />
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
            <thead style={{ color: 'var(--muted)', textAlign: 'left' }}>
              <tr>{['Time', 'Action', 'Resource', 'Safe data'].map(head => <th key={head} style={thStyle()}>{head}</th>)}</tr>
            </thead>
            <tbody>
              {(state.audit?.items ?? []).map(item => (
                <tr key={item.id}>
                  <td style={tdStyle()}>{formatTime(item.created_at)}</td>
                  <td style={tdStyle()}><strong>{item.action}</strong></td>
                  <td style={tdStyle()}>{item.resource_type} {item.resource_id ? item.resource_id.slice(0, 8) : ''}</td>
                  <td style={tdStyle()}>{safeDataLabel(item.data)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!loading && (state.audit?.items.length ?? 0) === 0 && <div style={{ padding: '18px', color: 'var(--muted)', textAlign: 'center' }}>No audit evidence yet.</div>}
        </div>
      </section>

      <section style={panelStyle()}>
        <SectionTitle icon={<FileText size={16} />} title="Channel Selector Snapshot" />
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '10px' }}>
          {(state.channels?.items ?? []).map(channel => (
            <div key={channel.id} style={rowStyle()}>
              <div>
                <div style={{ fontWeight: 850 }}>{channel.display_name}</div>
                <div style={mutedStyle()}>{channel.channel_type} - {channel.safe_display_id}</div>
              </div>
              <StatusPill ok={channel.is_selectable} label={channel.connection_status.toUpperCase()} />
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}

function MetricCard({ icon, label, value, tone }: { icon: ReactNode; label: string; value: number; tone: string }) {
  return <div style={panelStyle()}><div style={{ color: tone }}>{icon}</div><div style={mutedStyle()}>{label}</div><div style={{ fontSize: '28px', fontWeight: 850 }}>{value}</div></div>
}
function SectionTitle({ icon, title }: { icon: ReactNode; title: string }) { return <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 850, marginBottom: '12px' }}>{icon}{title}</div> }
function EmptyRow({ title, meta }: { title: string; meta: string }) { return <div style={rowStyle()}><div><div style={{ fontWeight: 850 }}>{title}</div><div style={mutedStyle()}>{meta}</div></div></div> }
function StatusPill({ ok, label }: { ok: boolean; label: string }) { return <span style={{ ...chipStyle(ok ? '#16a34a' : '#d97706'), whiteSpace: 'nowrap' }}>{label}</span> }
const SAFE_AUDIT_DATA_KEYS = new Set(['dry_run', 'status', 'resource_type', 'action', 'result', 'error_code', 'channel_type', 'platform', 'limit', 'count'])
const SENSITIVE_KEY_PATTERN = /(token|secret|cookie|credential|authorization|password|bearer|profile_url|external_id|fb_uid|facebook_id|page_id|user_id)/i
const SENSITIVE_VALUE_PATTERNS = [
  /https?:\/\/(?:www\.)?(?:facebook|fb)\.com\/\S*/i,
  /\bbearer\s+[a-z0-9._~+/=-]+/i,
  /\b(?:token|secret|cookie|credential)[\w .:=/-]*[a-z0-9._~+/=-]{6,}/i,
  /\b\d{12,}\b/,
]

function isSensitiveAuditValue(value: string) {
  return SENSITIVE_VALUE_PATTERNS.some(pattern => pattern.test(value))
}

function safeAuditValue(value: unknown) {
  if (typeof value === 'boolean') return String(value)
  if (typeof value === 'number') {
    const numericValue = String(value)
    return isSensitiveAuditValue(numericValue) ? null : numericValue
  }
  if (typeof value !== 'string') return null
  if (isSensitiveAuditValue(value)) return null
  return value.length > 80 ? `${value.slice(0, 77)}...` : value
}

function safeDataLabel(data: Record<string, unknown>) {
  const labels: string[] = []
  let redacted = 0

  for (const [key, value] of Object.entries(data)) {
    if (!SAFE_AUDIT_DATA_KEYS.has(key) || SENSITIVE_KEY_PATTERN.test(key)) {
      redacted += 1
      continue
    }
    const safeValue = safeAuditValue(value)
    if (safeValue === null) {
      redacted += 1
      continue
    }
    labels.push(`${key}=${safeValue}`)
  }

  if (redacted > 0) labels.push(`redacted_fields=${redacted}`)
  return labels.length ? labels.join(', ') : '-'
}
function formatTime(value: string) { const date = new Date(value); return Number.isNaN(date.getTime()) ? 'Invalid time' : date.toLocaleString('vi-VN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) }
function panelStyle(): CSSProperties { return { background: 'var(--card)', border: '1px solid var(--border)', borderRadius: '14px', padding: '16px' } }
function rowStyle(): CSSProperties { return { display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px', padding: '10px 12px', border: '1px solid var(--border)', borderRadius: '10px', background: 'var(--surface)' } }
function mutedStyle(): CSSProperties { return { color: 'var(--muted)', fontSize: '11px' } }
function chipStyle(color: string): CSSProperties { return { display: 'inline-flex', alignItems: 'center', justifyContent: 'center', border: `1px solid ${color}55`, background: `${color}12`, color, borderRadius: '999px', padding: '6px 9px', fontSize: '11px', fontWeight: 850 } }
function buttonStyle(background: string): CSSProperties { return { border: 0, borderRadius: '10px', background, color: '#fff', padding: '10px 12px', display: 'inline-flex', alignItems: 'center', gap: '8px', fontSize: '12px', fontWeight: 800, cursor: 'pointer' } }
function noticeStyle(color: string): CSSProperties { return { padding: '12px', borderRadius: '12px', background: `${color}12`, border: `1px solid ${color}55`, color, fontSize: '12px' } }
function thStyle(): CSSProperties { return { padding: '9px 8px', borderBottom: '1px solid var(--border)' } }
function tdStyle(): CSSProperties { return { padding: '10px 8px', borderBottom: '1px solid var(--border)' } }
