import { useState, useEffect, useCallback } from 'react'
import { fetchAPI, postAPI, deleteAPI } from '../api/client'
import type { Account } from '../types'

// ─── Types ───────────────────────────────────────────────────────────────────

interface Activity {
  id: string
  account_id: string
  action: string
  detail: string | null
  created_at: string
}

interface ExtensionStatus {
  id: string
  fb_uid: string | null
  extension_online: boolean
}

// ─── Helpers ────────────────────────────────────────────────────────────────

const STATUS_COLOR: Record<string, string> = {
  ACTIVE: 'var(--green)',
  PAUSED: 'var(--yellow)',
  BANNED: 'var(--red)',
  LOGGED_OUT: 'var(--muted)',
}

const STATUS_OPTIONS = ['ACTIVE', 'PAUSED', 'BANNED', 'LOGGED_OUT']

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const m = Math.floor(diff / 60000)
  if (m < 1) return 'just now'
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}

// ─── Sub-components ─────────────────────────────────────────────────────────

function StatBadge({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      background: 'var(--surface)', borderRadius: 6, padding: '6px 12px',
      border: '1px solid var(--border)', minWidth: 60,
    }}>
      <span style={{ fontSize: 18, fontWeight: 700, color }}>{value}</span>
      <span style={{ fontSize: 10, color: 'var(--muted)', textTransform: 'uppercase' }}>{label}</span>
    </div>
  )
}

function AccountRow({
  account,
  extensionOnline,
  onSelect,
  onDelete,
  onStatusChange,
}: {
  account: Account
  extensionOnline: boolean
  onSelect: (a: Account) => void
  onDelete: (id: string) => void
  onStatusChange: (id: string, status: string) => void
}) {
  const [changingStatus, setChangingStatus] = useState(false)

  async function handleStatusChange(newStatus: string) {
    setChangingStatus(true)
    await onStatusChange(account.id, newStatus)
    setChangingStatus(false)
  }

  return (
    <tr
      style={{ borderBottom: '1px solid var(--border)', cursor: 'pointer' }}
      onClick={() => onSelect(account)}
    >
      {/* Avatar + name + extension badge */}
      <td style={{ padding: '12px 16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ position: 'relative' }}>
            <div style={{
              width: 36, height: 36, borderRadius: '50%',
              background: 'var(--border)', display: 'flex', alignItems: 'center',
              justifyContent: 'center', fontSize: 16, flexShrink: 0,
              overflow: 'hidden',
            }}>
              {account.avatar_url
                ? <img src={account.avatar_url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                : '👤'
              }
            </div>
            {/* Extension online indicator dot */}
            <span title={extensionOnline ? 'Extension connected' : 'Extension offline'} style={{
              position: 'absolute', bottom: 0, right: 0,
              width: 10, height: 10, borderRadius: '50%',
              background: extensionOnline ? 'var(--green)' : 'var(--border)',
              border: '2px solid var(--card)',
              boxShadow: extensionOnline ? '0 0 6px var(--green)' : 'none',
            }} />
          </div>
          <div>
            <div style={{ fontWeight: 600, color: 'var(--text)' }}>{account.name}</div>
            <div style={{ fontSize: 11, color: 'var(--muted)' }}>
              {account.email || account.fb_uid || '—'}
            </div>
          </div>
        </div>
      </td>

      {/* Status */}
      <td style={{ padding: '12px 16px' }} onClick={e => e.stopPropagation()}>
        <select
          value={account.status}
          disabled={changingStatus}
          onChange={e => handleStatusChange(e.target.value)}
          style={{
            background: 'var(--card)', border: '1px solid var(--border)',
            color: STATUS_COLOR[account.status] || 'var(--text)',
            borderRadius: 4, padding: '4px 8px', fontSize: 12, cursor: 'pointer',
          }}
        >
          {STATUS_OPTIONS.map(s => (
            <option key={s} value={s} style={{ color: STATUS_COLOR[s] }}>{s}</option>
          ))}
        </select>
      </td>

      {/* Cookie status */}
      <td style={{ padding: '12px 16px', textAlign: 'center' }}>
        <span style={{
          display: 'inline-flex', alignItems: 'center', gap: 4,
          fontSize: 12, color: account.cookies_valid ? 'var(--green)' : 'var(--red)',
        }}>
          <span style={{
            width: 7, height: 7, borderRadius: '50%',
            background: account.cookies_valid ? 'var(--green)' : 'var(--red)',
          }} />
          {account.cookies_valid ? 'Valid' : 'Invalid'}
        </span>
      </td>

      {/* Daily counters */}
      <td style={{ padding: '12px 16px' }}>
        <div style={{ display: 'flex', gap: 8, fontSize: 11, color: 'var(--muted)' }}>
          <span>👍 {account.daily_likes ?? 0}</span>
          <span>💬 {account.daily_comments ?? 0}</span>
          <span>↗ {account.daily_posts ?? 0}</span>
          <span>✉ {account.daily_messages ?? 0}</span>
        </div>
      </td>

      {/* Last active */}
      <td style={{ padding: '12px 16px', fontSize: 11, color: 'var(--muted)' }}>
        {account.last_active ? relativeTime(account.last_active) : '—'}
      </td>

      {/* Actions */}
      <td style={{ padding: '12px 16px' }} onClick={e => e.stopPropagation()}>
        <button
          onClick={() => onDelete(account.id)}
          style={{
            background: 'transparent', border: '1px solid var(--border)',
            color: 'var(--red)', padding: '4px 10px', borderRadius: 4,
            cursor: 'pointer', fontSize: 12,
          }}
        >
          Delete
        </button>
      </td>
    </tr>
  )
}

// ─── Activity Drawer ─────────────────────────────────────────────────────────

function ActivityDrawer({ account, onClose }: { account: Account; onClose: () => void }) {
  const [logs, setLogs] = useState<Activity[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchAPI<Activity[]>(`/api/accounts/${account.id}/activities?limit=50`)
      .then(data => { setLogs(data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [account.id])

  return (
    <div style={{
      position: 'fixed', top: 0, right: 0, width: 380, height: '100vh',
      background: 'var(--surface)', borderLeft: '1px solid var(--border)',
      zIndex: 100, display: 'flex', flexDirection: 'column',
      boxShadow: '-4px 0 24px rgba(0,0,0,0.4)',
    }}>
      {/* Header */}
      <div style={{
        padding: '16px 20px', borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: 15 }}>{account.name}</div>
          <div style={{ fontSize: 11, color: STATUS_COLOR[account.status], marginTop: 2 }}>
            ● {account.status}
          </div>
        </div>
        <button onClick={onClose} style={{
          background: 'transparent', border: 'none', color: 'var(--muted)',
          fontSize: 20, cursor: 'pointer', padding: 4,
        }}>✕</button>
      </div>

      {/* Stats */}
      <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--border)' }}>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <StatBadge label="Likes" value={account.daily_likes ?? 0} color="var(--blue)" />
          <StatBadge label="Comments" value={account.daily_comments ?? 0} color="var(--purple)" />
          <StatBadge label="Posts" value={account.daily_posts ?? 0} color="var(--accent)" />
          <StatBadge label="Messages" value={account.daily_messages ?? 0} color="var(--yellow)" />
        </div>
        <div style={{ marginTop: 10, fontSize: 11, color: 'var(--muted)' }}>
          {account.email && <div>📧 {account.email}</div>}
          {account.profile_url && (
            <div>🔗 <a href={account.profile_url} target="_blank" rel="noreferrer"
              style={{ color: 'var(--accent)' }}>Profile</a></div>
          )}
          {account.notes && <div style={{ marginTop: 4, fontStyle: 'italic' }}>📝 {account.notes}</div>}
        </div>
      </div>

      {/* Activity log */}
      <div style={{ flex: 1, overflow: 'auto', padding: '12px 20px' }}>
        <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 10, textTransform: 'uppercase', letterSpacing: 1 }}>
          Activity Log
        </div>
        {loading ? (
          <div style={{ color: 'var(--muted)', fontSize: 12 }}>Loading…</div>
        ) : logs.length === 0 ? (
          <div style={{ color: 'var(--muted)', fontSize: 12 }}>No activity yet.</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {logs.map(log => (
              <div key={log.id} style={{
                background: 'var(--card)', borderRadius: 6, padding: '8px 12px',
                border: '1px solid var(--border)',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
                  <span style={{ fontSize: 12, color: 'var(--accent)', fontWeight: 600 }}>{log.action}</span>
                  <span style={{ fontSize: 10, color: 'var(--muted)' }}>{relativeTime(log.created_at)}</span>
                </div>
                {log.detail && (
                  <div style={{ fontSize: 11, color: 'var(--muted)', wordBreak: 'break-all' }}>{log.detail}</div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Create Account Modal ────────────────────────────────────────────────────

function CreateModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [form, setForm] = useState({ name: '', fb_uid: '', email: '', profile_url: '', notes: '' })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!form.name.trim()) { setError('Name is required'); return }
    setSaving(true)
    try {
      const body = Object.fromEntries(Object.entries(form).filter(([, v]) => v.trim()))
      await postAPI('/api/accounts', body)
      onCreated()
      onClose()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to create account')
    } finally {
      setSaving(false)
    }
  }

  const inputStyle: React.CSSProperties = {
    width: '100%', boxSizing: 'border-box',
    background: 'var(--card)', border: '1px solid var(--border)',
    color: 'var(--text)', borderRadius: 6, padding: '8px 12px',
    fontSize: 13, outline: 'none',
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 200,
    }} onClick={onClose}>
      <div style={{
        background: 'var(--surface)', border: '1px solid var(--border)',
        borderRadius: 12, padding: 28, width: 460, boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
      }} onClick={e => e.stopPropagation()}>
        <h3 style={{ margin: '0 0 20px', fontSize: 16 }}>➕ Add Account</h3>
        <form onSubmit={handleSubmit}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div>
              <label style={{ fontSize: 11, color: 'var(--muted)', display: 'block', marginBottom: 4 }}>
                Display Name *
              </label>
              <input
                style={inputStyle}
                placeholder="VD: Nguyen Van A"
                value={form.name}
                onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                autoFocus
              />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div>
                <label style={{ fontSize: 11, color: 'var(--muted)', display: 'block', marginBottom: 4 }}>FB UID</label>
                <input style={inputStyle} placeholder="100012345678" value={form.fb_uid}
                  onChange={e => setForm(f => ({ ...f, fb_uid: e.target.value }))} />
              </div>
              <div>
                <label style={{ fontSize: 11, color: 'var(--muted)', display: 'block', marginBottom: 4 }}>Email</label>
                <input style={inputStyle} placeholder="abc@gmail.com" value={form.email}
                  onChange={e => setForm(f => ({ ...f, email: e.target.value }))} />
              </div>
            </div>
            <div>
              <label style={{ fontSize: 11, color: 'var(--muted)', display: 'block', marginBottom: 4 }}>Profile URL</label>
              <input style={inputStyle} placeholder="https://facebook.com/..." value={form.profile_url}
                onChange={e => setForm(f => ({ ...f, profile_url: e.target.value }))} />
            </div>
            <div>
              <label style={{ fontSize: 11, color: 'var(--muted)', display: 'block', marginBottom: 4 }}>Notes</label>
              <input style={inputStyle} placeholder="Ghi chú tuỳ ý" value={form.notes}
                onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} />
            </div>
            {error && <div style={{ color: 'var(--red)', fontSize: 12 }}>⚠ {error}</div>}
            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 8 }}>
              <button type="button" onClick={onClose} style={{
                background: 'transparent', border: '1px solid var(--border)',
                color: 'var(--muted)', padding: '8px 18px', borderRadius: 6, cursor: 'pointer',
              }}>Hủy</button>
              <button type="submit" disabled={saving} style={{
                background: 'var(--accent)', border: 'none', color: '#fff',
                padding: '8px 20px', borderRadius: 6, cursor: 'pointer', fontWeight: 600,
                opacity: saving ? 0.7 : 1,
              }}>{saving ? 'Đang tạo…' : 'Tạo'}</button>
            </div>
          </div>
        </form>
      </div>
    </div>
  )
}

// ─── Main Page ───────────────────────────────────────────────────────────────

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [loading, setLoading] = useState(true)
  const [filterStatus, setFilterStatus] = useState<string>('ALL')
  const [search, setSearch] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [selected, setSelected] = useState<Account | null>(null)
  const [extStatus, setExtStatus] = useState<Record<string, boolean>>({})

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchAPI<Account[]>('/api/accounts')
      setAccounts(data)
    } finally {
      setLoading(false)
    }
  }, [])

  // Poll extension status every 10s
  const loadExtStatus = useCallback(async () => {
    try {
      const data = await fetchAPI<{ accounts: ExtensionStatus[] }>('/api/accounts/extension-status')
      const map: Record<string, boolean> = {}
      data.accounts.forEach(a => { map[a.id] = a.extension_online })
      setExtStatus(map)
    } catch {
      // silently ignore
    }
  }, [])

  useEffect(() => { load() }, [load])
  useEffect(() => {
    loadExtStatus()
    const interval = setInterval(loadExtStatus, 10_000)
    return () => clearInterval(interval)
  }, [loadExtStatus])

  async function handleDelete(id: string) {
    if (!confirm('Xoá account này?')) return
    await deleteAPI(`/api/accounts/${id}`)
    setAccounts(prev => prev.filter(a => a.id !== id))
    if (selected?.id === id) setSelected(null)
  }

  async function handleStatusChange(id: string, status: string) {
    const updated = await (await fetch(`/api/accounts/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    })).json() as Account
    setAccounts(prev => prev.map(a => a.id === id ? updated : a))
    if (selected?.id === id) setSelected(updated)
  }

  const displayed = accounts.filter(a => {
    if (filterStatus !== 'ALL' && a.status !== filterStatus) return false
    if (search && !a.name.toLowerCase().includes(search.toLowerCase()) &&
      !(a.email ?? '').toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  // Stats summary
  const stats = {
    total: accounts.length,
    active: accounts.filter(a => a.status === 'ACTIVE').length,
    paused: accounts.filter(a => a.status === 'PAUSED').length,
    banned: accounts.filter(a => a.status === 'BANNED').length,
    cookieOk: accounts.filter(a => a.cookies_valid).length,
  }

  return (
    <div style={{ padding: 28, maxWidth: 1100 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 24 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 22, fontWeight: 700 }}>Accounts</h2>
          <p style={{ margin: '4px 0 0', color: 'var(--muted)', fontSize: 13 }}>
            Quản lý tài khoản Facebook
          </p>
        </div>
        <button onClick={() => setShowCreate(true)} style={{
          background: 'var(--accent)', border: 'none', color: '#fff',
          padding: '9px 18px', borderRadius: 8, cursor: 'pointer',
          fontWeight: 600, fontSize: 13, display: 'flex', alignItems: 'center', gap: 6,
        }}>
          ＋ Add Account
        </button>
      </div>

      {/* Summary stat cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12, marginBottom: 24 }}>
        {[
          { label: 'Total', value: stats.total, color: 'var(--text)' },
          { label: 'Active', value: stats.active, color: 'var(--green)' },
          { label: 'Paused', value: stats.paused, color: 'var(--yellow)' },
          { label: 'Banned', value: stats.banned, color: 'var(--red)' },
          { label: 'Cookies OK', value: stats.cookieOk, color: 'var(--blue)' },
        ].map(s => (
          <div key={s.label} style={{
            background: 'var(--card)', border: '1px solid var(--border)',
            borderRadius: 10, padding: '14px 18px',
          }}>
            <div style={{ fontSize: 24, fontWeight: 700, color: s.color }}>{s.value}</div>
            <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2, textTransform: 'uppercase', letterSpacing: 0.5 }}>
              {s.label}
            </div>
          </div>
        ))}
      </div>

      {/* Toolbar */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 16, alignItems: 'center' }}>
        <input
          type="text"
          placeholder="🔍 Search name / email…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{
            flex: 1, background: 'var(--card)', border: '1px solid var(--border)',
            color: 'var(--text)', borderRadius: 6, padding: '8px 12px', fontSize: 13, outline: 'none',
          }}
        />
        <div style={{ display: 'flex', gap: 6 }}>
          {['ALL', ...STATUS_OPTIONS].map(s => (
            <button key={s} onClick={() => setFilterStatus(s)} style={{
              background: filterStatus === s ? 'var(--accent)' : 'var(--card)',
              border: '1px solid var(--border)',
              color: filterStatus === s ? '#fff' : 'var(--muted)',
              padding: '6px 14px', borderRadius: 6, cursor: 'pointer', fontSize: 12,
            }}>{s}</button>
          ))}
        </div>
        <button onClick={load} style={{
          background: 'var(--card)', border: '1px solid var(--border)',
          color: 'var(--muted)', padding: '6px 14px', borderRadius: 6, cursor: 'pointer', fontSize: 12,
        }}>↻ Refresh</button>
      </div>

      {/* Table */}
      <div style={{
        background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden',
      }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: 'var(--surface)' }}>
              {['Account', 'Status', 'Cookies', 'Today\'s Activity', 'Last Active', ''].map(h => (
                <th key={h} style={{
                  padding: '10px 16px', textAlign: 'left', fontSize: 11,
                  color: 'var(--muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5,
                }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={6} style={{ padding: 40, textAlign: 'center', color: 'var(--muted)' }}>Loading…</td></tr>
            ) : displayed.length === 0 ? (
              <tr>
                <td colSpan={6} style={{ padding: 48, textAlign: 'center', color: 'var(--muted)' }}>
                  {accounts.length === 0
                    ? 'Chưa có account nào. Nhấn "Add Account" để thêm.'
                    : 'Không có kết quả khớp.'}
                </td>
              </tr>
            ) : (
              displayed.map(acc => (
                <AccountRow
                  key={acc.id}
                  account={acc}
                  extensionOnline={extStatus[acc.id] ?? false}
                  onSelect={setSelected}
                  onDelete={handleDelete}
                  onStatusChange={handleStatusChange}
                />
              ))
            )}
          </tbody>
        </table>
      </div>

      <div style={{ marginTop: 10, fontSize: 11, color: 'var(--muted)' }}>
        {displayed.length} / {accounts.length} accounts · Click row to view activity
      </div>

      {/* Modals / Drawers */}
      {showCreate && (
        <CreateModal onClose={() => setShowCreate(false)} onCreated={load} />
      )}
      {selected && (
        <ActivityDrawer account={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  )
}
