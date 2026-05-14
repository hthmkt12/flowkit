import { useState, useEffect, useCallback } from 'react'
import { Activity, BarChart3, CheckCircle, Clock, Radio, ShieldCheck, Users, Wifi, WifiOff, XCircle } from 'lucide-react'
import { fetchAPI } from '../api/client'
import { useWebSocket } from '../api/useWebSocket'
import SafetyGateStatus from '../components/SafetyGateStatus'
import type { AgentStatus, DashboardPerformance, DashboardSummary, WSEvent } from '../types'

interface LiveEvent {
  id: number
  type: string
  text: string
  time: string
  color: string
}

let eventId = 0

function eventLabel(ev: WSEvent): { text: string; color: string } {
  const rawData = ev.data
  const data = rawData && typeof rawData === 'object' && !Array.isArray(rawData) ? rawData as Record<string, unknown> : {}
  const taskType = typeof data.type === 'string' ? data.type : ''
  const error = typeof data.error === 'string' ? data.error : 'không rõ lỗi'
  switch (ev.type) {
    case 'task_started':
      return { text: `Đang xử lý task ${taskType}`, color: 'var(--blue)' }
    case 'task_completed':
      return { text: `Hoàn tất task ${taskType}`, color: 'var(--green)' }
    case 'task_failed':
      return { text: `Task thất bại: ${error.slice(0, 60)}`, color: 'var(--red)' }
    case 'job.started':
      return { text: 'Chiến dịch đăng bài đã bắt đầu', color: 'var(--blue)' }
    case 'job.completed':
      return { text: 'Chiến dịch đăng bài đã hoàn tất', color: 'var(--green)' }
    default:
      return { text: ev.type, color: 'var(--muted)' }
  }
}

function statusLabel(value?: string) {
  if (value === 'ready') return { text: 'SẴN SÀNG', color: 'var(--green)' }
  if (value === 'not_synced') return { text: 'CHƯA ĐỒNG BỘ', color: 'var(--yellow)' }
  if (value === 'offline') return { text: 'OFFLINE', color: 'var(--red)' }
  return { text: 'CHƯA CẤU HÌNH', color: 'var(--muted)' }
}

function percentBar(value: number, color = 'var(--green)') {
  return (
    <div style={{ height: '7px', background: 'var(--border)', borderRadius: '999px', overflow: 'hidden' }}>
      <div style={{ height: '100%', width: `${Math.max(0, Math.min(100, value))}%`, background: color, borderRadius: '999px' }} />
    </div>
  )
}

export default function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [performance, setPerformance] = useState<DashboardPerformance | null>(null)
  const [agentStatus, setAgentStatus] = useState<AgentStatus | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [events, setEvents] = useState<LiveEvent[]>([])
  const { isConnected, lastEvent } = useWebSocket()

  const load = useCallback(async () => {
    const [status, dashboardSummary, dashboardPerformance] = await Promise.allSettled([
      fetchAPI<AgentStatus>('/api/status'),
      fetchAPI<DashboardSummary>('/api/dashboard/summary'),
      fetchAPI<DashboardPerformance>('/api/dashboard/performance?range=7d&limit=30'),
    ])

    setAgentStatus(status.status === 'fulfilled' ? status.value : null)
    setSummary(dashboardSummary.status === 'fulfilled' ? dashboardSummary.value : null)
    setPerformance(dashboardPerformance.status === 'fulfilled' ? dashboardPerformance.value : null)
    setLoadError(dashboardSummary.status === 'rejected' || dashboardPerformance.status === 'rejected' ? 'Không tải được dữ liệu ZooPost cloud.' : null)
  }, [])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    const timer = setInterval(load, 15_000)
    return () => clearInterval(timer)
  }, [load])

  useEffect(() => {
    if (!lastEvent) return
    const { text, color } = eventLabel(lastEvent)
    const time = new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    setEvents(prev => [{ id: ++eventId, type: lastEvent.type, text, time, color }, ...prev.slice(0, 49)])
  }, [lastEvent])

  const kpis = summary?.kpis ?? { scheduled_posts: 0, published_posts: 0, total_channels: 0, total_reach: 0 }
  const statusBar = summary?.status_bar ?? { buffer_api: 'not_configured', imgbb_api: 'not_configured', pancake: 'not_synced' }
  const cards = [
    { label: 'Bài viết đã đặt lịch', value: kpis.scheduled_posts, icon: <Clock size={18} />, color: 'var(--blue)', sub: '+0% so với tuần trước' },
    { label: 'Bài viết đã Public', value: kpis.published_posts, icon: <CheckCircle size={18} />, color: 'var(--green)', sub: '+0% so với tuần trước' },
    { label: 'Tổng kênh', value: kpis.total_channels, icon: <Users size={18} />, color: 'var(--purple)', sub: 'Fanpage/Profile/Nhóm' },
    { label: 'Tổng Reach', value: kpis.total_reach, icon: <Activity size={18} />, color: 'var(--yellow)', sub: 'Chỉ tính dữ liệu thật' },
  ]

  const maxChartValue = Math.max(1, ...(performance?.line_chart ?? []).map(row => Math.max(row.scheduled, row.published, row.failed)))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap' }}>
        <div>
          <div style={{ fontSize: '22px', fontWeight: 800, color: 'var(--text)' }}>Dashboard Tổng Quan</div>
          <div style={{ fontSize: '12px', color: 'var(--muted)' }}>Theo dõi lịch đăng, trạng thái bài viết và hiệu suất kênh từ ZooPost cloud.</div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', color: isConnected ? 'var(--green)' : 'var(--red)' }}>
          {isConnected ? <Wifi size={14} /> : <WifiOff size={14} />}
          {isConnected ? 'Realtime connected' : 'Realtime offline'}
        </div>
      </div>

      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', background: 'var(--card)', border: '1px solid var(--border)', borderRadius: '12px', padding: '10px 12px' }}>
        {[
          ['BUFFER API', statusBar.buffer_api],
          ['IMGBB API', statusBar.imgbb_api],
          ['PANCAKE', statusBar.pancake],
        ].map(([label, value]) => {
          const status = statusLabel(value)
          return (
            <div key={label} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', fontWeight: 700, color: status.color }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: status.color }} />
              {label}: {status.text}
            </div>
          )
        })}
      </div>

      {loadError && (
        <div style={{ border: '1px solid rgba(245,158,11,0.35)', background: 'rgba(245,158,11,0.08)', color: 'var(--yellow)', borderRadius: '12px', padding: '12px', fontSize: '12px' }}>
          {loadError} Hiển thị trạng thái an toàn thay vì dữ liệu giả.
        </div>
      )}

      <SafetyGateStatus status={agentStatus} />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: '12px' }}>
        {cards.map(card => (
          <div key={card.label} style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: '14px', padding: '16px', display: 'flex', flexDirection: 'column', gap: '9px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', color: card.color }}>
              {card.icon}
              <span style={{ fontSize: '11px', color: 'var(--muted)' }}>{card.sub}</span>
            </div>
            <div style={{ fontSize: '12px', color: 'var(--muted)', fontWeight: 700 }}>{card.label}</div>
            <div style={{ fontSize: '30px', color: 'var(--text)', fontWeight: 850, lineHeight: 1 }}>{card.value}</div>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.5fr) minmax(280px, 0.8fr)', gap: '12px' }}>
        <section style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: '14px', padding: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
            <div style={{ fontSize: '13px', fontWeight: 800 }}>Biểu đồ hiệu suất</div>
            <div style={{ fontSize: '11px', color: 'var(--muted)' }}>7 ngày</div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: `repeat(${performance?.line_chart.length || 7}, minmax(30px, 1fr))`, alignItems: 'end', gap: '8px', minHeight: '190px' }}>
            {(performance?.line_chart ?? []).map(row => (
              <div key={row.date} style={{ display: 'flex', flexDirection: 'column', gap: '5px', alignItems: 'stretch' }}>
                <div style={{ height: `${Math.max(4, row.scheduled / maxChartValue * 150)}px`, background: 'var(--blue)', borderRadius: '6px 6px 2px 2px' }} />
                <div style={{ height: `${Math.max(4, row.published / maxChartValue * 150)}px`, background: 'var(--green)', borderRadius: '6px 6px 2px 2px' }} />
                <div style={{ height: `${Math.max(4, row.failed / maxChartValue * 150)}px`, background: 'var(--yellow)', borderRadius: '6px 6px 2px 2px' }} />
                <div style={{ fontSize: '10px', color: 'var(--muted)', textAlign: 'center' }}>{row.date.slice(5)}</div>
              </div>
            ))}
          </div>
        </section>

        <section style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: '14px', padding: '16px' }}>
          <div style={{ fontSize: '13px', fontWeight: 800, marginBottom: '14px' }}>Tỷ lệ trạng thái bài viết</div>
          <div style={{ display: 'grid', placeItems: 'center', width: '130px', height: '130px', borderRadius: '50%', margin: '0 auto 16px', background: 'conic-gradient(var(--green) 0 55%, var(--yellow) 55% 75%, var(--border) 75% 100%)' }}>
            <div style={{ display: 'grid', placeItems: 'center', width: '88px', height: '88px', borderRadius: '50%', background: 'var(--card)' }}>
              <div style={{ fontSize: '26px', fontWeight: 850 }}>{performance?.status_donut.total ?? 0}</div>
              <div style={{ fontSize: '10px', color: 'var(--muted)' }}>Tổng</div>
            </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {(performance?.status_donut.segments ?? []).map(segment => (
              <div key={segment.status} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
                <span style={{ color: 'var(--muted)' }}>{segment.status}</span>
                <span style={{ fontWeight: 800 }}>{segment.count} ({segment.percent}%)</span>
              </div>
            ))}
          </div>
        </section>
      </div>

      <section style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: '14px', padding: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', fontWeight: 800, marginBottom: '12px' }}>
          <BarChart3 size={16} /> Hiệu suất theo kênh
        </div>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
            <thead style={{ color: 'var(--muted)', textAlign: 'left' }}>
              <tr>
                {['Kênh', 'Nền tảng', 'Đặt lịch', 'Public', 'Reach', 'Engagement', 'Tỷ lệ thành công'].map(head => <th key={head} style={{ padding: '9px 8px', borderBottom: '1px solid var(--border)' }}>{head}</th>)}
              </tr>
            </thead>
            <tbody>
              {(performance?.channel_performance ?? []).map(channel => (
                <tr key={channel.id}>
                  <td style={{ padding: '10px 8px', borderBottom: '1px solid var(--border)' }}>
                    <div style={{ fontWeight: 800 }}>{channel.display_name}</div>
                    <div style={{ fontSize: '10px', color: 'var(--muted)' }}>{channel.safe_display_id ?? 'ẩn định danh'}</div>
                  </td>
                  <td style={{ padding: '10px 8px', borderBottom: '1px solid var(--border)' }}>{channel.platform} / {channel.channel_type}</td>
                  <td style={{ padding: '10px 8px', borderBottom: '1px solid var(--border)' }}>{channel.scheduled}</td>
                  <td style={{ padding: '10px 8px', borderBottom: '1px solid var(--border)' }}>{channel.published}</td>
                  <td style={{ padding: '10px 8px', borderBottom: '1px solid var(--border)' }}>{channel.reach}</td>
                  <td style={{ padding: '10px 8px', borderBottom: '1px solid var(--border)' }}>{channel.engagement}</td>
                  <td style={{ padding: '10px 8px', borderBottom: '1px solid var(--border)', minWidth: '140px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ minWidth: '34px', fontWeight: 800 }}>{channel.success_rate}%</span>
                      <div style={{ flex: 1 }}>{percentBar(channel.success_rate)}</div>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {(performance?.channel_performance.length ?? 0) === 0 && <div style={{ color: 'var(--muted)', padding: '18px 0', textAlign: 'center' }}>Chưa có kênh nào.</div>}
        </div>
      </section>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '12px' }}>
        <BottomPanel title="Bài viết sắp tới" rows={(performance?.upcoming_posts ?? []).map(item => ({ id: item.target_id, title: item.channel_name, meta: `${item.status} · ${item.content_preview}` }))} />
        <BottomPanel title="Top performance content" rows={(performance?.top_content ?? []).map(item => ({ id: item.job_id, title: item.title ?? item.content_id, meta: item.body_preview }))} />
        <section style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: '14px', padding: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', fontWeight: 800, marginBottom: '12px' }}>
            <Radio size={15} /> Activity log gần đây
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '11px' }}>
            {events.map(event => (
              <div key={event.id} style={{ display: 'flex', gap: '8px' }}>
                <span style={{ color: 'var(--muted)' }}>{event.time}</span>
                <span style={{ color: event.color }}>{event.text}</span>
              </div>
            ))}
            {events.length === 0 && (performance?.activity_log ?? []).map(event => (
              <div key={event.id} style={{ color: 'var(--muted)' }}>{event.type}: {event.message}</div>
            ))}
            {events.length === 0 && (performance?.activity_log.length ?? 0) === 0 && <div style={{ color: 'var(--muted)' }}>Chưa có hoạt động.</div>}
          </div>
        </section>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--muted)', fontSize: '11px' }}>
        <ShieldCheck size={14} /> ZooPost cloud chỉ hiển thị dữ liệu thật; thao tác live vẫn bị chặn bởi FBKit Safety Gate.
        {loadError && <XCircle size={14} color="var(--yellow)" />}
      </div>
    </div>
  )
}

function BottomPanel({ title, rows }: { title: string; rows: { id: string; title: string | null; meta: string }[] }) {
  return (
    <section style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: '14px', padding: '16px' }}>
      <div style={{ fontSize: '13px', fontWeight: 800, marginBottom: '12px' }}>{title}</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {rows.length === 0 ? <div style={{ color: 'var(--muted)', fontSize: '12px' }}>Chưa có dữ liệu.</div> : rows.slice(0, 5).map(row => (
          <div key={row.id} style={{ borderBottom: '1px solid var(--border)', paddingBottom: '9px' }}>
            <div style={{ fontSize: '12px', fontWeight: 800 }}>{row.title || 'Không có tiêu đề'}</div>
            <div style={{ fontSize: '11px', color: 'var(--muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{row.meta}</div>
          </div>
        ))}
      </div>
    </section>
  )
}
