import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { CheckCircle, Clock, Image, Link, Play, RefreshCw, Search, Video, Wand2 } from 'lucide-react'
import { fetchAPI, postAPI } from '../api/client'
import type { ChannelSelectorItem, ChannelSelectorResponse, ContentItem, ContentPreviewResult, PublishJob, PublishJobProgress } from '../types'

const PLATFORM_COLOR: Record<string, string> = {
  facebook: '#2563eb',
  fanpage: '#2563eb',
  profile: '#7c3aed',
  group: '#d97706',
  youtube: '#dc2626',
  tiktok: '#111827',
  instagram: '#c026d3',
  pinterest: '#dc2626',
}

const ATTACHMENT_MODES = [
  { key: 'image', icon: Image, title: 'Đính kèm hình ảnh', desc: 'Tối đa 20 ảnh, dùng media asset đã đăng ký.' },
  { key: 'video', icon: Video, title: 'Đính kèm video', desc: 'Một video tối đa 500MB.' },
  { key: 'reup', icon: RefreshCw, title: 'Reup Media', desc: 'URL TikTok/YouTube/Instagram đã được backend kiểm tra.' },
  { key: 'background', icon: Wand2, title: 'Đính kèm nền', desc: 'Status background, dry-run preview trước.' },
  { key: 'link', icon: Link, title: 'Link chia sẻ Facebook', desc: 'Chỉ tạo job dry-run trong giai đoạn này.' },
]

const DEFAULT_BODY = 'Xin chào [r]\n$SPIN=[Nội dung A | Nội dung B | Nội dung C]'
const DEFAULT_TITLE = 'ZooPost dry-run'

type SavedContentDraft = { id: string; title: string; body: string }

export default function AutoPostFanpagePage() {
  const [channels, setChannels] = useState<ChannelSelectorItem[]>([])
  const [selected, setSelected] = useState<string[]>([])
  const [query, setQuery] = useState('')
  const [body, setBody] = useState(DEFAULT_BODY)
  const [title, setTitle] = useState(DEFAULT_TITLE)
  const savedContentRef = useRef<SavedContentDraft | null>(null)
  const saveSequence = useRef(0)
  const [preview, setPreview] = useState<ContentPreviewResult | null>(null)
  const [minDelay, setMinDelay] = useState(60)
  const [maxDelay, setMaxDelay] = useState(180)
  const [useSchedule, setUseSchedule] = useState(false)
  const [scheduledAt, setScheduledAt] = useState('')
  const [activeAttachment, setActiveAttachment] = useState('image')
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [job, setJob] = useState<PublishJob | null>(null)
  const [progress, setProgress] = useState<PublishJobProgress | null>(null)

  const loadChannels = useCallback(async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams({ platform: 'facebook', channel_type: 'fanpage', limit: '100' })
      if (query.trim()) params.set('search', query.trim())
      const data = await fetchAPI<ChannelSelectorResponse>(`/api/channels/selector?${params.toString()}`)
      setChannels(data.items)
      setMessage(null)
    } catch (error) {
      setChannels([])
      setMessage(error instanceof Error ? error.message : 'Không tải được danh sách kênh.')
    } finally {
      setLoading(false)
    }
  }, [query])

  useEffect(() => { loadChannels() }, [loadChannels])

  const filteredChannels = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return channels
    return channels.filter(channel => [channel.display_name, channel.username, channel.safe_display_id, channel.platform, channel.channel_type]
      .filter(Boolean)
      .some(value => String(value).toLowerCase().includes(needle)))
  }, [channels, query])

  const selectedChannels = channels.filter(channel => selected.includes(channel.id))
  const selectedFanpages = selectedChannels.filter(channel => channel.channel_type === 'fanpage').length
  const selectedOther = selectedChannels.length - selectedFanpages
  const normalizedMinDelay = Number.isFinite(minDelay) ? minDelay : 60
  const normalizedMaxDelay = Number.isFinite(maxDelay) ? maxDelay : 180
  const safeMinDelay = Math.max(60, Math.min(normalizedMinDelay, normalizedMaxDelay))
  const safeMaxDelay = Math.max(safeMinDelay, normalizedMaxDelay)
  const scheduledDate = useSchedule && scheduledAt ? new Date(scheduledAt) : null
  const validScheduledAt = scheduledDate && Number.isFinite(scheduledDate.getTime()) ? scheduledDate.toISOString() : null

  async function saveContent() {
    const cached = savedContentRef.current
    if (cached?.title === title && cached.body === body) return cached.id

    const draft = { title, body }
    const sequence = ++saveSequence.current
    const content = await postAPI<ContentItem>('/api/content-items', { ...draft, syntax_mode: 'zoopost', status: 'draft' })
    if (sequence === saveSequence.current) {
      const nextSaved = { id: content.id, ...draft }
      savedContentRef.current = nextSaved
      return content.id
    }
    return null
  }

  function updateTitle(value: string) {
    saveSequence.current += 1
    savedContentRef.current = null
    setTitle(value)
    setPreview(null)
  }

  function updateBody(value: string) {
    saveSequence.current += 1
    savedContentRef.current = null
    setBody(value)
    setPreview(null)
  }

  async function renderPreview() {
    const draft = { title, body }
    try {
      const savedContentId = await saveContent()
      if (!savedContentId || savedContentRef.current?.title !== draft.title || savedContentRef.current.body !== draft.body) return
      const params = new URLSearchParams({ seed: selected[0] ?? 'preview' })
      if (selected[0]) params.set('channel_id', selected[0])
      const result = await fetchAPI<ContentPreviewResult>(`/api/content-items/${savedContentId}/preview?${params.toString()}`)
      if (savedContentRef.current?.title !== draft.title || savedContentRef.current.body !== draft.body) return
      setPreview(result)
      setMessage(null)
    } catch (error) {
      setPreview(null)
      setMessage(error instanceof Error ? error.message : 'Không tạo được preview.')
    }
  }

  async function startDryRunJob() {
    if (!body.trim() || selected.length === 0) {
      setMessage('Nhập nội dung và chọn ít nhất một kênh trước khi tạo dry-run job.')
      return
    }
    if (useSchedule && !validScheduledAt) {
      setMessage('Chọn thời gian hẹn giờ hợp lệ trước khi tạo dry-run job.')
      return
    }
    setSubmitting(true)
    setJob(null)
    setProgress(null)
    try {
      const savedContentId = await saveContent()
      if (!savedContentId) {
        setMessage('Nội dung đã thay đổi trong lúc lưu. Bấm tạo dry-run lại để dùng bản mới nhất.')
        return
      }
      const created = await postAPI<PublishJob>('/api/publish-jobs', {
        content_item_id: savedContentId,
        channel_ids: selected,
        dry_run: true,
        schedule_mode: useSchedule ? 'scheduled' : 'draft',
        scheduled_at: useSchedule ? validScheduledAt : null,
        delay_policy: { min_delay_seconds: safeMinDelay, max_delay_seconds: safeMaxDelay },
      })
      setJob(created)
      const currentProgress = await fetchAPI<PublishJobProgress>(`/api/publish-jobs/${created.id}/progress`)
      setProgress(currentProgress)
      setMessage(`Đã tạo dry-run job ${created.id.slice(0, 8)} cho ${created.targets.length} kênh.`)
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Không tạo được dry-run job.')
    } finally {
      setSubmitting(false)
    }
  }

  function toggleChannel(channelId: string) {
    setSelected(prev => prev.includes(channelId) ? prev.filter(id => id !== channelId) : [...prev, channelId])
  }

  function selectAllVisible() {
    const visibleIds = filteredChannels.map(channel => channel.id)
    setSelected(prev => Array.from(new Set([...prev, ...visibleIds])))
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
        <div>
          <div style={{ fontSize: '22px', fontWeight: 850 }}>Auto Post Fanpage</div>
          <div style={{ fontSize: '12px', color: 'var(--muted)' }}>Tạo nội dung và publish job ở chế độ dry-run. Live posting vẫn bị chặn bởi Safety Gate.</div>
        </div>
        <button type="button" onClick={renderPreview} style={buttonStyle('#2563eb')}>
          <Wand2 size={14} /> Xem preview cú pháp
        </button>
      </div>

      {message && <div style={{ padding: '12px', borderRadius: '12px', background: 'rgba(37,99,235,0.08)', border: '1px solid rgba(37,99,235,0.25)', color: 'var(--accent)', fontSize: '12px' }}>{message}</div>}

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(280px, 1.1fr) minmax(260px, 0.8fr) minmax(300px, 0.9fr)', gap: '14px', alignItems: 'start' }}>
        <section style={panelStyle()}>
          <SectionTitle title="Cột 1 — Soạn nội dung" />
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', fontSize: '11px', color: 'var(--muted)' }}>
            {['[r] emoji vui', '[v] ngạc nhiên', '[a] buồn', '$SPIN=[oan a | oan b | oan c]'].map(item => <span key={item} style={chipStyle()}>{item}</span>)}
          </div>
          <input value={title} onChange={event => updateTitle(event.target.value)} placeholder="Tiêu đề nội dung" style={inputStyle()} />
          <textarea value={body} onChange={event => updateBody(event.target.value)} rows={12} style={{ ...inputStyle(), resize: 'vertical', lineHeight: 1.5 }} />
          {preview && <div style={{ background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: '12px', padding: '12px', fontSize: '12px', whiteSpace: 'pre-wrap' }}>{preview.body}</div>}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '8px' }}>
            {ATTACHMENT_MODES.map(mode => {
              const Icon = mode.icon
              const active = activeAttachment === mode.key
              return (
                <button key={mode.key} type="button" onClick={() => setActiveAttachment(mode.key)} style={{ ...cardButtonStyle(active), textAlign: 'left' }}>
                  <Icon size={16} />
                  <div style={{ fontWeight: 800 }}>{mode.title}</div>
                  <div style={{ fontSize: '10px', color: 'var(--muted)' }}>{mode.desc}</div>
                </button>
              )
            })}
          </div>
        </section>

        <section style={panelStyle()}>
          <SectionTitle title="Cột 2 — Cấu hình đăng bài" />
          <label style={labelStyle()}>Giãn cách random giữa mỗi lần đăng</label>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
            <input type="number" min={60} value={minDelay} onChange={event => setMinDelay(parseDelayInput(event.target.value, 60))} style={inputStyle()} />
            <input type="number" min={60} value={maxDelay} onChange={event => setMaxDelay(parseDelayInput(event.target.value, 180))} style={inputStyle()} />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '12px' }}>
            <label><input type="checkbox" disabled /> Chế độ nghỉ giữa phiên (chờ backend policy)</label>
            <label><input type="checkbox" checked={useSchedule} onChange={event => setUseSchedule(event.target.checked)} /> Hẹn giờ đăng</label>
          </div>
          {useSchedule && <input type="datetime-local" value={scheduledAt} onChange={event => setScheduledAt(event.target.value)} style={inputStyle()} />}
          <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '12px', padding: '12px', fontSize: '12px', color: 'var(--muted)' }}>
            {useSchedule ? (validScheduledAt ? `Dry-run job hẹn lúc ${new Date(validScheduledAt).toLocaleString('vi-VN')}` : 'Chọn thời gian hẹn giờ hợp lệ.') : 'Job sẽ được tạo ở trạng thái queued/dry-run.'}
          </div>
          <button type="button" disabled style={{ ...buttonStyle('#64748b'), opacity: 0.65 }}>CÀI ĐẶT SEEDING / PUSH FEED BACK</button>
        </section>

        <section style={panelStyle()}>
          <SectionTitle title="Cột 3 — Chọn Fanpage đăng bài" />
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <button type="button" onClick={loadChannels} style={smallButtonStyle()}><RefreshCw size={13} /> TẢI LẠI</button>
            <button type="button" onClick={selectAllVisible} style={smallButtonStyle()}>CHỌN TẤT CẢ</button>
          </div>
          <div style={{ position: 'relative' }}>
            <Search size={14} style={{ position: 'absolute', left: '10px', top: '11px', color: 'var(--muted)' }} />
            <input value={query} onChange={event => setQuery(event.target.value)} placeholder="Tìm kênh..." style={{ ...inputStyle(), paddingLeft: '30px' }} />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '430px', overflowY: 'auto' }}>
            {loading ? <div style={{ color: 'var(--muted)', fontSize: '12px' }}>Đang tải kênh...</div> : filteredChannels.map(channel => (
              <label key={channel.id} style={{ display: 'flex', gap: '10px', alignItems: 'center', padding: '10px', borderRadius: '12px', border: '1px solid var(--border)', background: selected.includes(channel.id) ? '#eff6ff' : 'var(--surface)' }}>
                <input type="checkbox" checked={selected.includes(channel.id)} onChange={() => toggleChannel(channel.id)} />
                <div style={{ width: '34px', height: '34px', borderRadius: '50%', background: PLATFORM_COLOR[channel.channel_type] ?? PLATFORM_COLOR[channel.platform] ?? 'var(--muted)', color: '#fff', display: 'grid', placeItems: 'center', fontWeight: 850 }}>{channel.display_name.slice(0, 1).toUpperCase()}</div>
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div style={{ fontSize: '12px', fontWeight: 850, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{channel.display_name}</div>
                  <div style={{ display: 'flex', gap: '6px', alignItems: 'center', fontSize: '10px', color: 'var(--muted)' }}>
                    <span style={{ ...chipStyle(), color: PLATFORM_COLOR[channel.channel_type] ?? PLATFORM_COLOR[channel.platform] }}>{channel.channel_type.toUpperCase()}</span>
                    <span>{channel.username ?? channel.safe_display_id ?? `${channel.channel_type}-${channel.id.slice(0, 8)}`}</span>
                  </div>
                </div>
              </label>
            ))}
            {!loading && filteredChannels.length === 0 && <div style={{ color: 'var(--muted)', fontSize: '12px', textAlign: 'center', padding: '24px' }}>Chưa có kênh phù hợp.</div>}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--muted)' }}>Đã chọn {selectedFanpages} Fanpage + {selectedOther} địa chỉ khác.</div>
          <button type="button" disabled style={{ ...buttonStyle('#2563eb'), opacity: 0.7 }}>+ THÊM TRANG CẦN ĐĂNG</button>
        </section>
      </div>

      <div style={{ position: 'sticky', bottom: 0, zIndex: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px', background: 'rgba(255,255,255,0.94)', border: '1px solid var(--border)', borderRadius: '14px', padding: '12px 14px', boxShadow: '0 10px 30px rgba(15,23,42,0.12)' }}>
        <div style={{ fontSize: '12px', color: 'var(--muted)' }}>
          Thời gian: {safeMinDelay}-{safeMaxDelay}s · Định dạng: {activeAttachment} · Fanpage: {selected.length} · Seeding: tắt · Ước tính: dry-run
        </div>
        <button type="button" onClick={startDryRunJob} disabled={submitting} style={buttonStyle('#16a34a')}>
          <Play size={15} /> {submitting ? 'ĐANG TẠO...' : 'BẮT ĐẦU ĐĂNG BÀI (DRY-RUN)'}
        </button>
      </div>

      {job && <ProgressPreview job={job} progress={progress} />}
    </div>
  )
}

function ProgressPreview({ job, progress }: { job: PublishJob; progress: PublishJobProgress | null }) {
  const counts = progress?.counts
  const total = counts?.total ?? job.targets.length
  const queued = counts?.queued ?? job.targets.filter(target => ['queued', 'retry'].includes(target.status)).length
  const failed = counts?.failed ?? job.targets.filter(target => target.status === 'failed').length
  const posted = counts?.posted ?? job.targets.filter(target => target.status === 'posted').length
  const dispatching = counts?.dispatching ?? 0
  const percent = progress?.percent_complete ?? (total === 0 ? 0 : Math.round((posted + failed) * 100 / total))
  return (
    <section style={panelStyle()}>
      <SectionTitle title="Modal — Tiến Trình Dry-run" />
      <div style={{ display: 'grid', gridTemplateColumns: '180px 1fr', gap: '16px' }}>
        <div style={{ display: 'grid', placeItems: 'center', width: '150px', height: '150px', borderRadius: '50%', background: `conic-gradient(var(--green) 0 ${percent}%, var(--border) ${percent}% 100%)` }}>
          <div style={{ display: 'grid', placeItems: 'center', width: '104px', height: '104px', borderRadius: '50%', background: 'var(--card)' }}>
            <div style={{ fontSize: '28px', fontWeight: 850 }}>{percent}%</div>
            <div style={{ fontSize: '10px', color: 'var(--muted)' }}>{progress?.status ?? job.status}</div>
          </div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {percentBar(percent)}
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <span style={chipStyle()}><CheckCircle size={12} /> Đã mô phỏng {posted}</span>
            <span style={chipStyle()}><Clock size={12} /> Đang xử lý {dispatching}</span>
            <span style={chipStyle()}>Đang chờ {queued}</span>
            <span style={chipStyle()}>Thất bại {failed}</span>
            <span style={chipStyle()}>Còn lại {Math.max(0, total - posted - failed)}</span>
          </div>
          {progress?.events[0] && <div style={{ fontSize: '12px', color: 'var(--muted)' }}>{progress.events[0].message}</div>}
          <div style={{ fontSize: '12px', color: 'var(--yellow)' }}>Đây là dry-run preview. Live posting vẫn cần Safety Gate và phê duyệt riêng.</div>
          <button type="button" disabled style={{ ...smallButtonStyle(), width: 'fit-content' }}>TẠM DỪNG</button>
        </div>
      </div>
    </section>
  )
}

function SectionTitle({ title }: { title: string }) {
  return <div style={{ fontSize: '13px', fontWeight: 850, marginBottom: '10px' }}>{title}</div>
}

function panelStyle(): React.CSSProperties {
  return { background: 'var(--card)', border: '1px solid var(--border)', borderRadius: '14px', padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }
}

function inputStyle(): React.CSSProperties {
  return { width: '100%', border: '1px solid var(--border)', background: 'var(--surface)', borderRadius: '10px', padding: '10px 12px', color: 'var(--text)', fontSize: '12px', outline: 'none' }
}

function labelStyle(): React.CSSProperties {
  return { color: 'var(--muted)', fontSize: '11px', fontWeight: 700 }
}

function chipStyle(): React.CSSProperties {
  return { display: 'inline-flex', alignItems: 'center', gap: '5px', borderRadius: '999px', background: 'var(--surface)', border: '1px solid var(--border)', padding: '4px 8px' }
}

function cardButtonStyle(active: boolean): React.CSSProperties {
  return { border: `1px solid ${active ? 'var(--accent)' : 'var(--border)'}`, background: active ? '#eff6ff' : 'var(--surface)', color: active ? 'var(--accent)' : 'var(--text)', borderRadius: '12px', padding: '10px', cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: '6px' }
}

function buttonStyle(background: string): React.CSSProperties {
  return { border: 0, borderRadius: '10px', background, color: '#fff', padding: '10px 14px', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: '8px', fontSize: '12px', fontWeight: 850, cursor: 'pointer' }
}

function smallButtonStyle(): React.CSSProperties {
  return { border: '1px solid var(--border)', borderRadius: '9px', background: 'var(--surface)', color: 'var(--text)', padding: '8px 10px', display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '11px', fontWeight: 750, cursor: 'pointer' }
}

function parseDelayInput(value: string, fallback: number) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

function percentBar(value: number) {
  return <div style={{ height: '8px', background: 'var(--border)', borderRadius: '999px', overflow: 'hidden' }}><div style={{ height: '100%', width: `${Math.max(0, Math.min(100, value))}%`, background: 'var(--green)' }} /></div>
}
