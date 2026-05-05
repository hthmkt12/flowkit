import { useState, useEffect, useCallback } from 'react'
import { Activity, Users, CheckCircle, XCircle, Clock, Zap, Eye, Wifi } from 'lucide-react'
import { fetchAPI } from '../api/client'
import { useWebSocket } from '../api/useWebSocket'
import type { TaskStats, Account, WSEvent } from '../types'

interface StatCard {
  label: string
  value: number | string
  icon: React.ReactNode
  color: string
  sub?: string
}

interface LiveEvent {
  id: number
  type: string
  text: string
  time: string
  color: string
}

let _evId = 0

function eventLabel(ev: WSEvent): { text: string; color: string } {
  const d = ev.data as Record<string, string>
  switch (ev.type) {
    case 'task_started':
      return { text: `▶ Task ${d.type} started`, color: 'var(--blue)' }
    case 'task_completed':
      return { text: `✓ Task ${d.type} completed`, color: 'var(--green)' }
    case 'task_failed':
      return { text: `✗ Task failed: ${d.error?.slice(0, 60)}`, color: 'var(--red)' }
    case 'seed_action':
      return { text: `🌱 Seeding: ${d.action} on ${d.target}`, color: 'var(--accent)' }
    case 'spy_new_ad':
      return { text: `👁 New ad found: ${d.page} — ${d.text?.slice(0, 50)}`, color: 'var(--yellow)' }
    case 'spy_check':
      return { text: `🔍 Spy check: ${d.target}`, color: 'var(--muted)' }
    case 'worker_break':
      return { text: `☕ Worker break (${d.duration_s}s)`, color: 'var(--muted)' }
    default:
      return { text: `${ev.type}`, color: 'var(--muted)' }
  }
}

export default function DashboardPage() {
  const [taskStats, setTaskStats] = useState<TaskStats>({})
  const [accounts, setAccounts] = useState<Account[]>([])
  const [seederStats, setSeederStats] = useState<{ campaigns: number; active: number }>({ campaigns: 0, active: 0 })
  const [spyStats, setSpyStats] = useState<{ targets: number; total_ads_found: number }>({ targets: 0, total_ads_found: 0 })
  const [events, setEvents] = useState<LiveEvent[]>([])
  const { isConnected, lastEvent } = useWebSocket()

  const load = useCallback(async () => {
    try {
      const [stats, accs, seed, spy] = await Promise.allSettled([
        fetchAPI<TaskStats>('/api/tasks/stats'),
        fetchAPI<Account[]>('/api/accounts'),
        fetchAPI<{ campaigns: number; active: number; running: boolean }>('/api/seeding/campaigns/stats'),
        fetchAPI<{ targets: number; total_ads_found: number; running: boolean }>('/api/spy/targets/stats'),
      ])
      if (stats.status === 'fulfilled') setTaskStats(stats.value)
      if (accs.status === 'fulfilled') setAccounts(accs.value)
      if (seed.status === 'fulfilled') setSeederStats(seed.value)
      if (spy.status === 'fulfilled') setSpyStats(spy.value)
    } catch {}
  }, [])

  useEffect(() => { load() }, [load])

  // Refresh stats every 15s
  useEffect(() => {
    const t = setInterval(load, 15_000)
    return () => clearInterval(t)
  }, [load])

  // Add live event to feed
  useEffect(() => {
    if (!lastEvent) return
    const { text, color } = eventLabel(lastEvent)
    const now = new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    setEvents(prev => [{ id: ++_evId, type: lastEvent.type, text, time: now, color }, ...prev.slice(0, 49)])
  }, [lastEvent])

  const activeAccounts = accounts.filter(a => a.status === 'ACTIVE').length
  const totalTasks = Object.values(taskStats).reduce((a, b) => a + b, 0)

  const cards: StatCard[] = [
    {
      label: 'Tasks Total',
      value: totalTasks,
      icon: <Activity size={18} />,
      color: 'var(--accent)',
      sub: `${taskStats.PENDING ?? 0} pending · ${taskStats.PROCESSING ?? 0} running`,
    },
    {
      label: 'Completed',
      value: taskStats.COMPLETED ?? 0,
      icon: <CheckCircle size={18} />,
      color: 'var(--green)',
      sub: `${taskStats.FAILED ?? 0} failed`,
    },
    {
      label: 'Accounts',
      value: accounts.length,
      icon: <Users size={18} />,
      color: 'var(--blue)',
      sub: `${activeAccounts} active`,
    },
    {
      label: 'Seeding',
      value: seederStats.active,
      icon: <Zap size={18} />,
      color: 'var(--yellow)',
      sub: `${seederStats.campaigns} total campaigns`,
    },
    {
      label: 'Spy Targets',
      value: spyStats.targets,
      icon: <Eye size={18} />,
      color: 'var(--purple)',
      sub: `${spyStats.total_ads_found} ads found`,
    },
    {
      label: 'Pending Queue',
      value: taskStats.PENDING ?? 0,
      icon: <Clock size={18} />,
      color: 'var(--muted)',
      sub: `${taskStats.CANCELLED ?? 0} cancelled`,
    },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Status bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', color: 'var(--muted)' }}>
        <Wifi size={13} color={isConnected ? 'var(--green)' : 'var(--red)'} />
        <span style={{ color: isConnected ? 'var(--green)' : 'var(--red)' }}>
          {isConnected ? 'Live' : 'Disconnected'}
        </span>
        <span>·</span>
        <span>FBKit Agent Dashboard</span>
      </div>

      {/* Stat cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '12px' }}>
        {cards.map(card => (
          <div key={card.label} style={{
            background: 'var(--card)',
            border: '1px solid var(--border)',
            borderRadius: '10px',
            padding: '16px',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: card.color }}>
              {card.icon}
              <span style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--muted)' }}>
                {card.label}
              </span>
            </div>
            <div style={{ fontSize: '28px', fontWeight: 700, color: 'var(--text)', lineHeight: 1 }}>
              {card.value}
            </div>
            {card.sub && (
              <div style={{ fontSize: '11px', color: 'var(--muted)' }}>{card.sub}</div>
            )}
          </div>
        ))}
      </div>

      {/* Bottom grid: task breakdown + live feed */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', minHeight: '300px' }}>
        {/* Task breakdown */}
        <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: '10px', padding: '16px' }}>
          <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--muted)', marginBottom: '16px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Task Breakdown
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {[
              { label: 'Completed', key: 'COMPLETED', color: 'var(--green)' },
              { label: 'Failed', key: 'FAILED', color: 'var(--red)' },
              { label: 'Pending', key: 'PENDING', color: 'var(--yellow)' },
              { label: 'Processing', key: 'PROCESSING', color: 'var(--accent)' },
              { label: 'Cancelled', key: 'CANCELLED', color: 'var(--muted)' },
            ].map(row => {
              const v = (taskStats as Record<string, number>)[row.key] ?? 0
              const pct = totalTasks > 0 ? Math.round((v / totalTasks) * 100) : 0
              return (
                <div key={row.key}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', marginBottom: '4px' }}>
                    <span style={{ color: 'var(--text)' }}>{row.label}</span>
                    <span style={{ color: row.color, fontWeight: 600 }}>{v} ({pct}%)</span>
                  </div>
                  <div style={{ height: '4px', background: 'var(--border)', borderRadius: '2px', overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${pct}%`, background: row.color, borderRadius: '2px', transition: 'width 0.5s ease' }} />
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Live event feed */}
        <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: '10px', padding: '16px', display: 'flex', flexDirection: 'column' }}>
          <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--muted)', marginBottom: '12px', textTransform: 'uppercase', letterSpacing: '0.05em', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ display: 'inline-block', width: '6px', height: '6px', borderRadius: '50%', background: isConnected ? 'var(--green)' : 'var(--red)', animation: isConnected ? 'pulse 2s infinite' : 'none' }} />
            Live Feed
          </div>
          <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '11px' }}>
            {events.length === 0 ? (
              <div style={{ color: 'var(--muted)', margin: 'auto' }}>Waiting for events…</div>
            ) : events.map(ev => (
              <div key={ev.id} style={{ display: 'flex', gap: '8px', alignItems: 'flex-start' }}>
                <span style={{ color: 'var(--muted)', flexShrink: 0, fontFamily: 'monospace' }}>{ev.time}</span>
                <span style={{ color: ev.color, wordBreak: 'break-word' }}>{ev.text}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Accounts quick view */}
      {accounts.length > 0 && (
        <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: '10px', padding: '16px' }}>
          <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--muted)', marginBottom: '12px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Accounts ({accounts.length})
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '8px' }}>
            {accounts.slice(0, 12).map(acc => (
              <div key={acc.id} style={{
                display: 'flex', alignItems: 'center', gap: '8px',
                padding: '8px 10px', borderRadius: '8px', background: 'var(--surface)',
                border: '1px solid var(--border)',
              }}>
                <span style={{
                  width: '7px', height: '7px', borderRadius: '50%', flexShrink: 0,
                  background: acc.status === 'ACTIVE' ? 'var(--green)' : acc.status === 'BANNED' ? 'var(--red)' : 'var(--muted)',
                }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: '12px', fontWeight: 500, color: 'var(--text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{acc.name}</div>
                  <div style={{ fontSize: '10px', color: 'var(--muted)' }}>
                    👍{acc.daily_likes} 💬{acc.daily_comments} 📝{acc.daily_posts}
                  </div>
                </div>
                <XCircle size={12} color={acc.cookies_valid ? 'var(--green)' : 'var(--red)'} />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
