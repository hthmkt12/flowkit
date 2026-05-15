import { useState, useEffect, useCallback } from 'react'
import { Plus, Square, Trash2, RefreshCw } from 'lucide-react'
import { fetchAPI, postAPI, deleteAPI } from '../api/client'
import type { SeedCampaign } from '../types'

const STATUS_COLOR: Record<string, string> = {
  ACTIVE: 'var(--green)',
  PAUSED: 'var(--yellow)',
  COMPLETED: 'var(--muted)',
  CANCELLED: 'var(--red)',
}

export default function SeedingPage() {
  const [campaigns, setCampaigns] = useState<SeedCampaign[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({
    name: '',
    accounts: '',    // comma-separated account IDs
    targets: '',     // comma-separated post URLs
    actions: 'LIKE',
    comments: '',
    delay_min: '60',
    delay_max: '300',
  })

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchAPI<SeedCampaign[]>('/api/seeding/campaigns')
      setCampaigns(data)
    } catch (error) {
      void error
    }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  async function create() {
    if (!form.name || !form.targets) return
    await postAPI('/api/seeding/campaigns', {
      name: form.name,
      accounts: form.accounts.split(',').map(s => s.trim()).filter(Boolean),
      targets: form.targets.split('\n').map(s => s.trim()).filter(Boolean),
      actions: form.actions.split(',').map(s => s.trim()),
      comments: form.comments.split('\n').map(s => s.trim()).filter(Boolean),
      delay_min: Number(form.delay_min),
      delay_max: Number(form.delay_max),
    })
    setShowCreate(false)
    setForm({ name: '', accounts: '', targets: '', actions: 'LIKE', comments: '', delay_min: '60', delay_max: '300' })
    load()
  }

  async function stop(id: string) {
    await postAPI(`/api/seeding/campaigns/${id}/stop`, {})
    load()
  }

  async function remove(id: string) {
    if (!confirm('Xóa campaign này?')) return
    await deleteAPI(`/api/seeding/campaigns/${id}`)
    load()
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text)' }}>Seeding Campaigns</div>
          <div style={{ fontSize: '11px', color: 'var(--muted)', marginTop: '2px' }}>
            Tự động like / comment / share trên nhiều tài khoản
          </div>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button onClick={load} style={btnStyle('var(--surface)')}>
            <RefreshCw size={13} /> Refresh
          </button>
          <button onClick={() => setShowCreate(v => !v)} style={btnStyle('var(--accent)')}>
            <Plus size={13} /> New Campaign
          </button>
        </div>
      </div>

      {/* Create form */}
      {showCreate && (
        <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: '10px', padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text)' }}>Tạo Campaign Mới</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
            <label style={labelStyle}>
              <span>Tên Campaign</span>
              <input value={form.name} onChange={e => setForm(f => ({...f, name: e.target.value}))} style={inputStyle} placeholder="VD: Like Group A" />
            </label>
            <label style={labelStyle}>
              <span>Actions (LIKE, COMMENT, SHARE)</span>
              <input value={form.actions} onChange={e => setForm(f => ({...f, actions: e.target.value}))} style={inputStyle} placeholder="LIKE,COMMENT" />
            </label>
            <label style={labelStyle}>
              <span>Account IDs (cách nhau bằng dấu phẩy)</span>
              <input value={form.accounts} onChange={e => setForm(f => ({...f, accounts: e.target.value}))} style={inputStyle} placeholder="uuid1,uuid2" />
            </label>
            <label style={labelStyle}>
              <span>Delay (giây): min – max</span>
              <div style={{ display: 'flex', gap: '6px' }}>
                <input value={form.delay_min} onChange={e => setForm(f => ({...f, delay_min: e.target.value}))} style={{...inputStyle, width: '80px'}} type="number" />
                <span style={{ color: 'var(--muted)', alignSelf: 'center' }}>–</span>
                <input value={form.delay_max} onChange={e => setForm(f => ({...f, delay_max: e.target.value}))} style={{...inputStyle, width: '80px'}} type="number" />
              </div>
            </label>
          </div>
          <label style={labelStyle}>
            <span>Post URLs (mỗi dòng một URL)</span>
            <textarea value={form.targets} onChange={e => setForm(f => ({...f, targets: e.target.value}))}
              style={{...inputStyle, height: '80px', resize: 'vertical'}} placeholder="https://fb.com/..." />
          </label>
          <label style={labelStyle}>
            <span>Comments pool (mỗi dòng một câu)</span>
            <textarea value={form.comments} onChange={e => setForm(f => ({...f, comments: e.target.value}))}
              style={{...inputStyle, height: '60px', resize: 'vertical'}} placeholder="Great post!\nTuyệt vời 👍" />
          </label>
          <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
            <button onClick={() => setShowCreate(false)} style={btnStyle('var(--surface)')}>Hủy</button>
            <button onClick={create} style={btnStyle('var(--green)')}>Tạo</button>
          </div>
        </div>
      )}

      {/* Campaign list */}
      {loading ? (
        <div style={{ color: 'var(--muted)', fontSize: '12px' }}>Đang tải…</div>
      ) : campaigns.length === 0 ? (
        <div style={{ color: 'var(--muted)', fontSize: '13px', textAlign: 'center', padding: '40px' }}>
          Chưa có campaign nào. Nhấn "New Campaign" để tạo.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {campaigns.map(c => (
            <div key={c.id} style={{
              background: 'var(--card)', border: '1px solid var(--border)',
              borderRadius: '10px', padding: '14px 16px',
              display: 'flex', alignItems: 'center', gap: '12px',
            }}>
              {/* Status dot */}
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: STATUS_COLOR[c.status] ?? 'var(--muted)', flexShrink: 0 }} />

              {/* Info */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text)' }}>{c.name}</div>
                <div style={{ fontSize: '11px', color: 'var(--muted)', marginTop: '3px', display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                  <span>👤 {c.accounts.length} accounts</span>
                  <span>🎯 {c.targets.length} targets</span>
                  <span>⚡ {c.actions.join(', ')}</span>
                </div>
              </div>

              {/* Stats */}
              <div style={{ textAlign: 'right', flexShrink: 0 }}>
                <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text)' }}>
                  {c.stats.success}/{c.stats.total}
                </div>
                <div style={{ fontSize: '10px', color: c.stats.failed > 0 ? 'var(--red)' : 'var(--muted)' }}>
                  {c.stats.failed} failed
                </div>
              </div>

              {/* Status badge */}
              <span style={{ fontSize: '10px', fontWeight: 600, padding: '2px 8px', borderRadius: '999px', background: 'var(--surface)', color: STATUS_COLOR[c.status] ?? 'var(--muted)', flexShrink: 0 }}>
                {c.status}
              </span>

              {/* Actions */}
              <div style={{ display: 'flex', gap: '4px', flexShrink: 0 }}>
                {c.status === 'ACTIVE' && (
                  <button onClick={() => stop(c.id)} title="Tạm dừng" style={iconBtn('var(--yellow)')}>
                    <Square size={13} />
                  </button>
                )}
                <button onClick={() => remove(c.id)} title="Xóa" style={iconBtn('var(--red)')}>
                  <Trash2 size={13} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

const btnStyle = (bg: string): React.CSSProperties => ({
  display: 'flex', alignItems: 'center', gap: '5px',
  padding: '6px 12px', borderRadius: '6px', border: 'none',
  background: bg, color: 'var(--text)', fontSize: '12px',
  cursor: 'pointer', fontWeight: 500,
})

const iconBtn = (color: string): React.CSSProperties => ({
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  width: '28px', height: '28px', borderRadius: '6px', border: 'none',
  background: 'var(--surface)', color, cursor: 'pointer',
})

const labelStyle: React.CSSProperties = {
  display: 'flex', flexDirection: 'column', gap: '4px',
  fontSize: '11px', color: 'var(--muted)', fontWeight: 500,
}

const inputStyle: React.CSSProperties = {
  background: 'var(--surface)', border: '1px solid var(--border)',
  borderRadius: '6px', padding: '6px 8px', color: 'var(--text)',
  fontSize: '12px', outline: 'none', width: '100%', boxSizing: 'border-box',
}
