import { useCallback, useEffect, useMemo, useState } from 'react'
import type { CSSProperties, ReactNode } from 'react'
import { CheckCircle, Copy, PlugZap, RefreshCw, ShieldCheck, Terminal, XCircle } from 'lucide-react'
import { fetchAPI, postAPI } from '../api/client'
import type { AgentInstallation, AgentInstallationCreateResponse, AgentSessionReadiness } from '../types'

export default function AgentOnboardingPage() {
  const [installations, setInstallations] = useState<AgentInstallation[]>([])
  const [sessions, setSessions] = useState<Record<string, AgentSessionReadiness[]>>({})
  const [selectedId, setSelectedId] = useState('')
  const [name, setName] = useState('FBKit Local Agent')
  const [registrationToken, setRegistrationToken] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const selected = installations.find(item => item.id === selectedId) ?? installations[0] ?? null
  const selectedSessions = selected ? sessions[selected.id] ?? [] : []
  const readySessions = selectedSessions.filter(session => session.dry_run_ready)
  const setupCommand = useMemo(() => {
    if (!selected || !registrationToken.trim()) return ''
    return `$env:ZOOPOST_CLOUD_BEARER_TOKEN="<zoopost-user-jwt>"\n.\\.venv\\Scripts\\python.exe scripts\\zoopost-agent-env-setup.py --cloud-url http://127.0.0.1:8200 --installation-id ${selected.id} --registration-token ${registrationToken.trim()}`
  }, [registrationToken, selected])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const items = await fetchAPI<AgentInstallation[]>('/api/agent-installations')
      setInstallations(items)
      const sessionPairs = await Promise.all(items.map(async item => [item.id, await fetchAPI<AgentSessionReadiness[]>(`/api/agent-installations/${item.id}/sessions`)] as const))
      setSessions(Object.fromEntries(sessionPairs))
      setMessage(null)
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Không tải được trạng thái agent.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  async function createInstallation() {
    if (!name.trim()) {
      setMessage('Nhập tên agent trước khi tạo kết nối.')
      return
    }
    setLoading(true)
    try {
      const created = await postAPI<AgentInstallationCreateResponse>('/api/agent-installations', { name })
      setRegistrationToken(created.registration_token)
      setSelectedId(created.id)
      setInstallations(prev => [created, ...prev.filter(item => item.id !== created.id)])
      setMessage('Đã tạo token đăng ký. Copy token này sang máy chạy FBKit local trong 15 phút.')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Không tạo được agent installation.')
    } finally {
      setLoading(false)
    }
  }

  async function copySetup() {
    if (!setupCommand) return
    await navigator.clipboard.writeText(setupCommand)
    setMessage('Đã copy lệnh local helper. Exchange credential chỉ chạy trên máy local.')
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
        <div>
          <div style={{ fontSize: '22px', fontWeight: 850 }}>Kết nối Agent</div>
          <div style={{ fontSize: '12px', color: 'var(--muted)' }}>Pair ZooPost Cloud với FBKit local ở chế độ dry-run. Cloud không lưu cookie, profile trình duyệt hoặc credential Facebook.</div>
        </div>
        <button type="button" onClick={load} disabled={loading} style={buttonStyle('#2563eb')}><RefreshCw size={14} /> Làm mới</button>
      </div>

      {message && <div style={noticeStyle()}>{message}</div>}

      <section style={panelStyle()}>
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center', marginBottom: '12px' }}><ShieldCheck size={18} color="#16a34a" /><strong>Safety boundary</strong></div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '10px', fontSize: '12px' }}>
          {['LIVE_ACTIONS_ENABLED=false', 'DRY_RUN_DEFAULT=true', 'APPROVAL_REQUIRED=true', 'API_AUTH_ENABLED=false', 'WS_AUTH_ENABLED=false', 'Không có live arm / approval / real posting'].map(item => <div key={item} style={safetyChipStyle()}>{item}</div>)}
        </div>
      </section>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(300px, 0.9fr) minmax(320px, 1.1fr)', gap: '14px', alignItems: 'start' }}>
        <section style={panelStyle()}>
          <SectionTitle icon={<PlugZap size={16} />} title="Bước 1 — Tạo installation" />
          <input value={name} onChange={event => setName(event.target.value)} placeholder="Tên agent" style={inputStyle()} />
          <button type="button" onClick={createInstallation} disabled={loading} style={buttonStyle('#16a34a')}>Tạo agent installation</button>

          <label style={labelStyle()}>Agent installation</label>
          <select value={selected?.id ?? ''} onChange={event => setSelectedId(event.target.value)} style={inputStyle()}>
            {installations.map(item => <option key={item.id} value={item.id}>{item.name} — {item.status}</option>)}
          </select>

          {selected && <div style={metaBoxStyle()}>
            <div>ID: {selected.id}</div>
            <div>Token generation: {selected.token_generation}</div>
            <div>Credential last used: {selected.credential_last_used_at ?? 'chưa dùng'}</div>
          </div>}
        </section>

        <section style={panelStyle()}>
          <SectionTitle icon={<Terminal size={16} />} title="Bước 2 — Chạy exchange trên máy local" />
          <textarea value={registrationToken} onChange={event => setRegistrationToken(event.target.value)} rows={3} placeholder="Registration token chỉ dùng một lần" style={inputStyle()} />
          <div style={{ fontSize: '12px', color: 'var(--muted)', marginBottom: '10px' }}>Dashboard không nhận long-lived agent credential. Copy lệnh này sang terminal local để exchange token và in env command an toàn.</div>
          {setupCommand && <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <pre style={codeStyle()}>{setupCommand}</pre>
            <button type="button" onClick={copySetup} style={buttonStyle('#0f766e')}><Copy size={14} /> Copy local helper command</button>
          </div>}
        </section>
      </div>

      <section style={panelStyle()}>
        <SectionTitle icon={<CheckCircle size={16} />} title="Bước 3 — Readiness dry-run" />
        <div style={{ fontSize: '12px', color: 'var(--muted)', marginBottom: '10px' }}>Ready = online session + capability <code>publish-dry-run</code> + ít nhất một Facebook profile.</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '10px' }}>
          {selectedSessions.map(session => <SessionCard key={session.id} session={session} />)}
          {selectedSessions.length === 0 && <div style={metaBoxStyle()}>Chưa có session. Chạy FBKit local bằng env command sau khi exchange token.</div>}
        </div>
        <div style={{ marginTop: '12px', fontSize: '12px', fontWeight: 800, color: readySessions.length ? '#16a34a' : '#dc2626' }}>
          {readySessions.length ? `${readySessions.length} session sẵn sàng dry-run.` : 'Chưa sẵn sàng dry-run.'}
        </div>
      </section>
    </div>
  )
}

function SessionCard({ session }: { session: AgentSessionReadiness }) {
  const Icon = session.dry_run_ready ? CheckCircle : XCircle
  return <div style={{ ...metaBoxStyle(), borderColor: session.dry_run_ready ? 'rgba(22,163,74,0.35)' : 'rgba(220,38,38,0.25)' }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 850 }}><Icon size={16} /> {session.status}</div>
    <div>Capabilities: {session.capability_names.join(', ') || 'none'}</div>
    <div>Facebook profiles: {session.has_facebook_profile ? session.connected_profile_count : 0}</div>
    <div>Last heartbeat: {session.last_heartbeat_at ?? 'none'}</div>
  </div>
}

function SectionTitle({ icon, title }: { icon: ReactNode; title: string }) {
  return <div style={{ display: 'flex', gap: '8px', alignItems: 'center', fontWeight: 850, marginBottom: '12px' }}>{icon}{title}</div>
}

function panelStyle(): CSSProperties { return { background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: '16px', padding: '16px', boxShadow: 'var(--shadow)' } }
function inputStyle(): CSSProperties { return { width: '100%', border: '1px solid var(--border)', borderRadius: '10px', padding: '10px 12px', fontSize: '12px', marginBottom: '10px', background: '#fff' } }
function labelStyle(): CSSProperties { return { display: 'block', fontSize: '11px', fontWeight: 800, color: 'var(--muted)', margin: '10px 0 6px' } }
function buttonStyle(background: string): CSSProperties { return { border: 0, borderRadius: '10px', background, color: '#fff', padding: '10px 12px', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: '8px', fontSize: '12px', fontWeight: 800, cursor: 'pointer' } }
function noticeStyle(): CSSProperties { return { padding: '12px', borderRadius: '12px', background: 'rgba(37,99,235,0.08)', border: '1px solid rgba(37,99,235,0.25)', color: 'var(--accent)', fontSize: '12px' } }
function safetyChipStyle(): CSSProperties { return { padding: '10px', borderRadius: '10px', background: 'rgba(22,163,74,0.08)', border: '1px solid rgba(22,163,74,0.25)', color: '#166534', fontWeight: 800 } }
function metaBoxStyle(): CSSProperties { return { background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '12px', padding: '12px', fontSize: '12px', color: 'var(--muted)', display: 'flex', flexDirection: 'column', gap: '6px' } }
function codeStyle(): CSSProperties { return { margin: 0, background: '#0f172a', color: '#e2e8f0', borderRadius: '12px', padding: '12px', overflowX: 'auto', fontSize: '11px', whiteSpace: 'pre-wrap' } }
