import { useState, useEffect, useCallback } from 'react'
import { RefreshCw, Trash2 } from 'lucide-react'
import { fetchAPI, deleteAPI } from '../api/client'
import type { Task, TaskStatus } from '../types'

const STATUS_COLOR: Record<TaskStatus, string> = {
  PENDING: 'var(--yellow)',
  PROCESSING: 'var(--accent)',
  COMPLETED: 'var(--green)',
  FAILED: 'var(--red)',
  CANCELLED: 'var(--muted)',
}

const ALL_STATUSES: TaskStatus[] = ['PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', 'CANCELLED']

export default function TasksPage() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [filter, setFilter] = useState<TaskStatus | ''>('')
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const url = filter ? `/api/tasks?status=${filter}` : '/api/tasks'
      const data = await fetchAPI<Task[]>(url)
      setTasks(data)
    } catch (error) {
      void error
    }
    finally { setLoading(false) }
  }, [filter])

  useEffect(() => { load() }, [load])

  async function cancel(id: string) {
    await deleteAPI(`/api/tasks/${id}`)
    load()
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* Header + filters */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
        <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text)', marginRight: '8px' }}>Task Queue</div>
        {(['', ...ALL_STATUSES] as const).map(s => (
          <button
            key={s}
            onClick={() => setFilter(s as TaskStatus | '')}
            style={{
              padding: '4px 10px', borderRadius: '999px', border: 'none', fontSize: '11px',
              fontWeight: 600, cursor: 'pointer',
              background: filter === s ? (s ? STATUS_COLOR[s as TaskStatus] : 'var(--accent)') : 'var(--surface)',
              color: filter === s ? '#fff' : 'var(--muted)',
              transition: 'all 0.15s',
            }}
          >
            {s || 'All'}
          </button>
        ))}
        <button onClick={load} style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '5px', padding: '5px 10px', borderRadius: '6px', border: 'none', background: 'var(--surface)', color: 'var(--muted)', fontSize: '12px', cursor: 'pointer' }}>
          <RefreshCw size={13} /> Refresh
        </button>
      </div>

      {/* Task table */}
      {loading ? (
        <div style={{ color: 'var(--muted)', fontSize: '12px' }}>Đang tải…</div>
      ) : tasks.length === 0 ? (
        <div style={{ color: 'var(--muted)', fontSize: '13px', textAlign: 'center', padding: '40px' }}>Không có task nào</div>
      ) : (
        <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: '10px', overflow: 'hidden' }}>
          {/* Table header */}
          <div style={rowStyle(true)}>
            <span style={{ flex: 2 }}>ID</span>
            <span style={{ flex: 3 }}>Type</span>
            <span style={{ flex: 2 }}>Account</span>
            <span style={{ flex: 2 }}>Status</span>
            <span style={{ flex: 2 }}>Created</span>
            <span style={{ flex: 3 }}>Error</span>
            <span style={{ flex: 1 }} />
          </div>

          {/* Table rows */}
          {tasks.map((t, i) => (
            <div key={t.id} style={{ ...rowStyle(false), background: i % 2 === 0 ? 'var(--card)' : 'var(--surface)' }}>
              <span style={{ flex: 2, fontFamily: 'monospace', fontSize: '10px', color: 'var(--muted)' }}>
                {t.id.slice(0, 8)}…
              </span>
              <span style={{ flex: 3, fontSize: '11px', fontWeight: 600, color: 'var(--text)' }}>
                {t.task_type}
              </span>
              <span style={{ flex: 2, fontSize: '10px', color: 'var(--muted)', fontFamily: 'monospace' }}>
                {t.account_id?.slice(0, 8) ?? 'system'}
              </span>
              <span style={{ flex: 2 }}>
                <span style={{ fontSize: '10px', fontWeight: 600, padding: '2px 8px', borderRadius: '999px', background: 'var(--surface)', color: STATUS_COLOR[t.status] }}>
                  {t.status}
                </span>
                {t.retry_count > 0 && (
                  <span style={{ fontSize: '10px', color: 'var(--muted)', marginLeft: '4px' }}>×{t.retry_count}</span>
                )}
              </span>
              <span style={{ flex: 2, fontSize: '10px', color: 'var(--muted)' }}>
                {new Date(t.created_at).toLocaleString('vi-VN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })}
              </span>
              <span style={{ flex: 3, fontSize: '10px', color: 'var(--red)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={t.error_message ?? ''}>
                {t.error_message ?? '—'}
              </span>
              <span style={{ flex: 1, display: 'flex', justifyContent: 'flex-end' }}>
                {(t.status === 'PENDING' || t.status === 'PROCESSING') && (
                  <button onClick={() => cancel(t.id)} title="Cancel" style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--muted)' }}>
                    <Trash2 size={12} />
                  </button>
                )}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function rowStyle(isHeader: boolean): React.CSSProperties {
  return {
    display: 'flex', alignItems: 'center', gap: '8px',
    padding: '10px 14px',
    borderBottom: '1px solid var(--border)',
    fontSize: isHeader ? '10px' : '11px',
    fontWeight: isHeader ? 600 : 400,
    color: isHeader ? 'var(--muted)' : 'var(--text)',
    textTransform: isHeader ? 'uppercase' : 'none',
    letterSpacing: isHeader ? '0.05em' : 'normal',
  }
}
