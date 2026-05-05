import { useState, useEffect, useCallback } from 'react'
import { Plus, Trash2, RefreshCw, Eye } from 'lucide-react'
import { fetchAPI, postAPI, deleteAPI } from '../api/client'
import type { SpyTarget, SpyAd } from '../types'

export default function SpyPage() {
  const [targets, setTargets] = useState<SpyTarget[]>([])
  const [ads, setAds] = useState<SpyAd[]>([])
  const [selectedTarget, setSelectedTarget] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ page_name: '', page_id: '', page_url: '', check_interval: '3600' })

  const loadTargets = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchAPI<SpyTarget[]>('/api/spy/targets')
      setTargets(data)
    } catch {}
    finally { setLoading(false) }
  }, [])

  const loadAds = useCallback(async (targetId?: string) => {
    const url = targetId ? `/api/spy/ads?target_id=${targetId}` : '/api/spy/ads'
    try {
      const data = await fetchAPI<SpyAd[]>(url)
      setAds(data)
    } catch {}
  }, [])

  useEffect(() => { loadTargets() }, [loadTargets])
  useEffect(() => { loadAds(selectedTarget || undefined) }, [loadAds, selectedTarget])

  async function create() {
    if (!form.page_name || !form.page_id) return
    await postAPI('/api/spy/targets', {
      page_name: form.page_name,
      page_id: form.page_id,
      page_url: form.page_url || null,
      check_interval: Number(form.check_interval),
    })
    setShowCreate(false)
    setForm({ page_name: '', page_id: '', page_url: '', check_interval: '3600' })
    loadTargets()
  }

  async function remove(id: string) {
    if (!confirm('Xóa spy target này?')) return
    await deleteAPI(`/api/spy/targets/${id}`)
    if (selectedTarget === id) setSelectedTarget('')
    loadTargets()
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text)' }}>Spy Ads</div>
          <div style={{ fontSize: '11px', color: 'var(--muted)', marginTop: '2px' }}>
            Theo dõi quảng cáo đối thủ trên Facebook Ad Library
          </div>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button onClick={() => { loadTargets(); loadAds(selectedTarget || undefined) }} style={btnStyle('var(--surface)')}>
            <RefreshCw size={13} /> Refresh
          </button>
          <button onClick={() => setShowCreate(v => !v)} style={btnStyle('var(--accent)')}>
            <Plus size={13} /> Thêm Target
          </button>
        </div>
      </div>

      {/* Create form */}
      {showCreate && (
        <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: '10px', padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text)' }}>Thêm Spy Target</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
            <label style={labelStyle}>
              <span>Tên Page</span>
              <input value={form.page_name} onChange={e => setForm(f => ({...f, page_name: e.target.value}))} style={inputStyle} placeholder="Nike Vietnam" />
            </label>
            <label style={labelStyle}>
              <span>Page ID (Facebook ID)</span>
              <input value={form.page_id} onChange={e => setForm(f => ({...f, page_id: e.target.value}))} style={inputStyle} placeholder="123456789" />
            </label>
            <label style={labelStyle}>
              <span>Page URL (tùy chọn)</span>
              <input value={form.page_url} onChange={e => setForm(f => ({...f, page_url: e.target.value}))} style={inputStyle} placeholder="https://fb.com/nike" />
            </label>
            <label style={labelStyle}>
              <span>Check interval (giây)</span>
              <input value={form.check_interval} onChange={e => setForm(f => ({...f, check_interval: e.target.value}))} style={inputStyle} type="number" />
            </label>
          </div>
          <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
            <button onClick={() => setShowCreate(false)} style={btnStyle('var(--surface)')}>Hủy</button>
            <button onClick={create} style={btnStyle('var(--green)')}>Thêm</button>
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr', gap: '12px', minHeight: '400px' }}>
        {/* Target list */}
        <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: '10px', padding: '12px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '4px' }}>
            Targets ({targets.length})
          </div>
          {loading ? (
            <div style={{ color: 'var(--muted)', fontSize: '12px' }}>Đang tải…</div>
          ) : targets.length === 0 ? (
            <div style={{ color: 'var(--muted)', fontSize: '12px', textAlign: 'center', padding: '20px' }}>
              Chưa có target nào
            </div>
          ) : targets.map(t => (
            <div
              key={t.id}
              onClick={() => setSelectedTarget(prev => prev === t.id ? '' : t.id)}
              style={{
                padding: '10px 12px', borderRadius: '8px', cursor: 'pointer',
                background: selectedTarget === t.id ? 'var(--accent)' : 'var(--surface)',
                border: `1px solid ${selectedTarget === t.id ? 'var(--accent)' : 'var(--border)'}`,
                transition: 'all 0.15s',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ fontSize: '12px', fontWeight: 600, color: selectedTarget === t.id ? '#fff' : 'var(--text)' }}>
                  {t.page_name}
                </div>
                <button onClick={e => { e.stopPropagation(); remove(t.id) }} style={{ background: 'none', border: 'none', cursor: 'pointer', color: selectedTarget === t.id ? '#fff' : 'var(--red)', opacity: 0.7 }}>
                  <Trash2 size={12} />
                </button>
              </div>
              <div style={{ fontSize: '10px', color: selectedTarget === t.id ? 'rgba(255,255,255,0.7)' : 'var(--muted)', marginTop: '4px', display: 'flex', gap: '10px' }}>
                <span>👁 {t.ads_found} ads</span>
                <span style={{ color: t.status === 'ACTIVE' ? (selectedTarget === t.id ? '#7fffaa' : 'var(--green)') : 'var(--muted)' }}>
                  {t.status}
                </span>
              </div>
              {t.last_checked && (
                <div style={{ fontSize: '10px', color: selectedTarget === t.id ? 'rgba(255,255,255,0.5)' : 'var(--muted)', marginTop: '2px' }}>
                  Last: {new Date(t.last_checked).toLocaleString('vi-VN')}
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Ads panel */}
        <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: '10px', padding: '16px', display: 'flex', flexDirection: 'column' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Eye size={12} />
            Discovered Ads {selectedTarget ? `— ${targets.find(t => t.id === selectedTarget)?.page_name}` : '(tất cả)'}
          </div>
          <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {ads.length === 0 ? (
              <div style={{ color: 'var(--muted)', fontSize: '12px', textAlign: 'center', padding: '40px' }}>
                {selectedTarget ? 'Chưa phát hiện ad nào cho target này' : 'Chưa có ad nào. Chọn một target để xem.'}
              </div>
            ) : ads.map(ad => (
              <div key={ad.id} style={{
                background: 'var(--surface)', border: '1px solid var(--border)',
                borderRadius: '8px', padding: '12px',
              }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '8px' }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--accent)', marginBottom: '4px' }}>
                      {ad.page_name ?? '—'} {ad.fb_ad_id ? `· ID: ${ad.fb_ad_id}` : ''}
                    </div>
                    {ad.ad_text && (
                      <div style={{ fontSize: '12px', color: 'var(--text)', lineHeight: 1.5, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                        {ad.ad_text.slice(0, 300)}
                        {ad.ad_text.length > 300 && '…'}
                      </div>
                    )}
                    {ad.media_url && (
                      <div style={{ marginTop: '6px' }}>
                        <a href={ad.media_url} target="_blank" rel="noreferrer" style={{ fontSize: '11px', color: 'var(--blue)' }}>
                          🖼 Media URL
                        </a>
                      </div>
                    )}
                  </div>
                  <div style={{ flexShrink: 0, textAlign: 'right' }}>
                    <div style={{ fontSize: '10px', color: ad.ad_status === 'ACTIVE' ? 'var(--green)' : 'var(--muted)', fontWeight: 600 }}>
                      {ad.ad_status}
                    </div>
                    <div style={{ fontSize: '10px', color: 'var(--muted)', marginTop: '2px' }}>
                      {new Date(ad.first_seen).toLocaleDateString('vi-VN')}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

const btnStyle = (bg: string): React.CSSProperties => ({
  display: 'flex', alignItems: 'center', gap: '5px',
  padding: '6px 12px', borderRadius: '6px', border: 'none',
  background: bg, color: 'var(--text)', fontSize: '12px',
  cursor: 'pointer', fontWeight: 500,
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
