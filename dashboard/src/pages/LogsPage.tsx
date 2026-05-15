import { useState, useEffect, useCallback } from 'react'
import { RefreshCw } from 'lucide-react'
import { fetchAPI } from '../api/client'

interface ActivityLog {
  id: number
  account_id: string | null
  action: string
  detail: string | null
  created_at: string
}

export default function LogsPage() {
  const [logs, setLogs] = useState<ActivityLog[]>([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchAPI<ActivityLog[]>('/api/accounts/activity')
      setLogs(data)
    } catch (error) {
      void error
    }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text)' }}>Activity Logs</div>
          <div style={{ fontSize: '11px', color: 'var(--muted)', marginTop: '2px' }}>Lịch sử hoạt động của các tài khoản</div>
        </div>
        <button onClick={load} style={{ display: 'flex', alignItems: 'center', gap: '5px', padding: '5px 10px', borderRadius: '6px', border: 'none', background: 'var(--surface)', color: 'var(--muted)', fontSize: '12px', cursor: 'pointer' }}>
          <RefreshCw size={13} /> Refresh
        </button>
      </div>

      <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: '10px', overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: '24px', color: 'var(--muted)', fontSize: '12px' }}>Đang tải…</div>
        ) : logs.length === 0 ? (
          <div style={{ padding: '40px', color: 'var(--muted)', fontSize: '13px', textAlign: 'center' }}>Không có log nào</div>
        ) : logs.map((log, i) => (
          <div key={log.id} style={{
            display: 'flex', alignItems: 'center', gap: '12px',
            padding: '10px 16px',
            borderBottom: '1px solid var(--border)',
            background: i % 2 === 0 ? 'var(--card)' : 'var(--surface)',
            fontSize: '12px',
          }}>
            <span style={{ color: 'var(--muted)', fontFamily: 'monospace', fontSize: '10px', flexShrink: 0, whiteSpace: 'nowrap' }}>
              {new Date(log.created_at).toLocaleString('vi-VN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            </span>
            <span style={{ color: 'var(--muted)', fontFamily: 'monospace', fontSize: '10px', flexShrink: 0 }}>
              {log.account_id?.slice(0, 8) ?? 'system'}
            </span>
            <span style={{ fontWeight: 600, color: 'var(--accent)', flexShrink: 0 }}>{log.action}</span>
            <span style={{ color: 'var(--text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {log.detail ?? ''}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
