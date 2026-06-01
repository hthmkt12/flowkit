import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { CheckCircle, Clock, Image, Link, Play, RefreshCw, Search, Video, Wand2 } from 'lucide-react'
import { fetchAPI, postAPI } from '../api/client'
import type { ChannelSelectorItem, ChannelSelectorResponse, ContentItem, ContentPreviewResult, MediaAsset, PublishJob, PublishJobProgress, SocialChannel } from '../types'

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
const PUBLISH_PROGRESS_POLL_MS = 3000
const PUBLISH_TERMINAL_STATUSES = new Set(['posted', 'completed', 'failed', 'cancelled'])
const PUBLISH_POLLING_STOP_STATUSES = new Set([...PUBLISH_TERMINAL_STATUSES, 'paused'])

type SavedContentDraft = { id: string; title: string; body: string; mediaAssetIds: string[] }
type ReadinessDiagnostic = { key: string; title: string; detail: string; status: string }

function sameMediaAssets(left: string[], right: string[]) {
  return left.length === right.length && left.every((id, index) => id === right[index])
}

function channelReadinessDetail(channel: ChannelSelectorItem) {
  const supportedTaskTypes = Array.isArray(channel.supported_task_types) ? channel.supported_task_types : []
  if (channel.disabled_reason === 'channel_not_ready' || channel.connection_status !== 'ready') return 'Agent/kênh chưa ready cho dry-run.'
  if (channel.disabled_reason === 'mvp_live_scope_facebook_fanpage_only') return 'Chỉ hỗ trợ Facebook Fanpage trong flow dry-run này.'
  if (!channel.is_selectable) return 'Kênh chưa sẵn sàng cho dry-run.'
  if (!supportedTaskTypes.some(taskType => taskType.startsWith('facebook.post_'))) return 'Kênh chưa khai báo capability publish cho Facebook post.'
  if (channel.disabled_reason) return 'Kênh chưa sẵn sàng cho dry-run.'
  return null
}

function selectedChannelDiagnostics(channels: ChannelSelectorItem[], selectedIds: string[]): ReadinessDiagnostic[] {
  return channels
    .filter(channel => selectedIds.includes(channel.id))
    .map(channel => {
      const detail = channelReadinessDetail(channel)
      return detail ? { key: channel.id, title: channel.display_name, detail, status: channel.connection_status } : null
    })
    .filter((item): item is ReadinessDiagnostic => item !== null)
}

function isPublishTerminalStatus(status: string | null | undefined) {
  return status ? PUBLISH_TERMINAL_STATUSES.has(status) : false
}

function shouldStopPublishPolling(status: string | null | undefined, targets: Array<{ status: string }>) {
  if (targets.some(target => target.status === 'dispatching')) return false
  return status ? PUBLISH_POLLING_STOP_STATUSES.has(status) : false
}

export default function AutoPostFanpagePage() {
  const [channels, setChannels] = useState<ChannelSelectorItem[]>([])
  const [selected, setSelected] = useState<string[]>([])
  const [query, setQuery] = useState('')
  const [body, setBody] = useState(DEFAULT_BODY)
  const [title, setTitle] = useState(DEFAULT_TITLE)
  const savedContentRef = useRef<SavedContentDraft | null>(null)
  const activeJobIdRef = useRef<string | null>(null)
  const historyLoadSequence = useRef(0)
  const saveSequence = useRef(0)
  const [preview, setPreview] = useState<ContentPreviewResult | null>(null)
  const [mediaAssets, setMediaAssets] = useState<MediaAsset[]>([])
  const [selectedMediaIds, setSelectedMediaIds] = useState<string[]>([])
  const [mediaUrl, setMediaUrl] = useState('')
  const [mediaMimeType, setMediaMimeType] = useState('image/png')
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
  const [progressPollTick, setProgressPollTick] = useState(0)
  const [jobHistory, setJobHistory] = useState<PublishJob[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [jobActionPending, setJobActionPending] = useState<string | null>(null)
  const [newChannelName, setNewChannelName] = useState('')
  const [newChannelUsername, setNewChannelUsername] = useState('')
  const [creatingChannel, setCreatingChannel] = useState(false)

  const loadChannels = useCallback(async (search = query) => {
    setLoading(true)
    try {
      const params = new URLSearchParams({ platform: 'facebook', channel_type: 'fanpage', limit: '100' })
      if (search.trim()) params.set('search', search.trim())
      const data = await fetchAPI<ChannelSelectorResponse>(`/api/channels/selector?${params.toString()}`)
      setChannels(data.items)
      setMessage(null)
    } catch {
      setChannels([])
      setMessage('Không tải được danh sách kênh.')
    } finally {
      setLoading(false)
    }
  }, [query])

  useEffect(() => { loadChannels() }, [loadChannels])

  const loadMediaAssets = useCallback(async () => {
    try {
      const data = await fetchAPI<MediaAsset[]>('/api/media-assets')
      setMediaAssets(data)
    } catch {
      setMediaAssets([])
      setMessage('Không tải được media assets.')
    }
  }, [])

  useEffect(() => { loadMediaAssets() }, [loadMediaAssets])

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
  const readinessDiagnostics = selectedChannelDiagnostics(channels, selected)
  const normalizedMinDelay = Number.isFinite(minDelay) ? minDelay : 60
  const normalizedMaxDelay = Number.isFinite(maxDelay) ? maxDelay : 180
  const safeMinDelay = Math.max(60, Math.min(normalizedMinDelay, normalizedMaxDelay))
  const safeMaxDelay = Math.max(safeMinDelay, normalizedMaxDelay)
  const scheduledDate = useSchedule && scheduledAt ? new Date(scheduledAt) : null
  const validScheduledAt = scheduledDate && Number.isFinite(scheduledDate.getTime()) ? scheduledDate.toISOString() : null
  const refreshProgress = useCallback(async (jobId: string) => {
    try {
      const currentProgress = await fetchAPI<PublishJobProgress>(`/api/publish-jobs/${jobId}/progress`)
      if (activeJobIdRef.current === jobId) setProgress(currentProgress)
      return currentProgress
    } catch {
      if (activeJobIdRef.current === jobId) setMessage('Không tải được tiến trình dry-run.')
      return null
    }
  }, [])

  const loadJobHistory = useCallback(async () => {
    const sequence = ++historyLoadSequence.current
    setHistoryLoading(true)
    try {
      const jobs = await fetchAPI<PublishJob[]>('/api/publish-jobs?limit=5')
      if (sequence === historyLoadSequence.current) setJobHistory(jobs.filter(item => item.dry_run).slice(0, 5))
    } catch {
      if (sequence === historyLoadSequence.current) setMessage('Không tải được lịch sử dry-run.')
    } finally {
      if (sequence === historyLoadSequence.current) setHistoryLoading(false)
    }
  }, [])

  useEffect(() => { loadJobHistory() }, [loadJobHistory])

  const jobTargetStatusKey = (progress?.targets ?? job?.targets ?? []).map(target => `${target.id}:${target.status}`).join('|')
  const shouldStopCurrentJobPolling = job ? shouldStopPublishPolling(progress?.status ?? job.status, progress?.targets ?? job.targets) : true

  useEffect(() => {
    if (!job || shouldStopCurrentJobPolling) return
    const timer = window.setTimeout(async () => {
      await refreshProgress(job.id)
      if (activeJobIdRef.current === job.id) setProgressPollTick(tick => tick + 1)
    }, PUBLISH_PROGRESS_POLL_MS)
    return () => window.clearTimeout(timer)
  }, [job, shouldStopCurrentJobPolling, progressPollTick, refreshProgress, jobTargetStatusKey])

  async function saveContent() {
    const cached = savedContentRef.current
    if (cached?.title === title && cached.body === body && sameMediaAssets(cached.mediaAssetIds, selectedMediaIds)) return cached.id

    const draft = { title, body, mediaAssetIds: [...selectedMediaIds] }
    const sequence = ++saveSequence.current
    const content = await postAPI<ContentItem>('/api/content-items', { title: draft.title, body: draft.body, media_asset_ids: draft.mediaAssetIds, syntax_mode: 'zoopost', status: 'draft' })
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

  function toggleMediaAsset(mediaId: string) {
    saveSequence.current += 1
    savedContentRef.current = null
    setSelectedMediaIds(prev => prev.includes(mediaId) ? prev.filter(id => id !== mediaId) : [...prev, mediaId])
    setPreview(null)
  }

  async function createMediaAsset() {
    if (!mediaUrl.trim()) {
      setMessage('Nhập URL media trước khi thêm attachment.')
      return
    }
    try {
      const created = await postAPI<MediaAsset>('/api/media-assets', { type: activeAttachment === 'video' ? 'video' : 'image', source: 'external_url', url: mediaUrl.trim(), mime_type: mediaMimeType.trim() || null })
      setMediaAssets(prev => [created, ...prev])
      setSelectedMediaIds(prev => prev.includes(created.id) ? prev : [...prev, created.id])
      setMediaUrl('')
      setMessage('Đã thêm media asset vào bản nháp.')
      saveSequence.current += 1
      savedContentRef.current = null
      setPreview(null)
    } catch {
      setMessage('Không tạo được media asset.')
    }
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
    } catch {
      setPreview(null)
      setMessage('Không tạo được preview.')
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
    if (readinessDiagnostics.length > 0) {
      setMessage('Chưa thể tạo dry-run job vì có kênh chưa sẵn sàng.')
      return
    }
    setSubmitting(true)
    activeJobIdRef.current = null
    setJob(null)
    setProgress(null)
    setProgressPollTick(0)
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
      activeJobIdRef.current = created.id
      setJob(created)
      await refreshProgress(created.id)
      await loadJobHistory()
      setMessage(`Đã tạo dry-run job ${created.id.slice(0, 8)} cho ${created.targets.length} kênh.`)
    } catch {
      setMessage('Không tạo được dry-run job.')
    } finally {
      setSubmitting(false)
    }
  }

  async function openHistoryJob(nextJob: PublishJob) {
    activeJobIdRef.current = nextJob.id
    setJob(nextJob)
    setProgress(null)
    setProgressPollTick(0)
    await refreshProgress(nextJob.id)
  }

  async function runJobAction(action: 'pause' | 'cancel' | 'retry', targetId?: string) {
    if (!job) return
    const actionKey = targetId ? `${action}:${targetId}` : action
    setJobActionPending(actionKey)
    try {
      const path = action === 'retry'
        ? `/api/publish-jobs/${job.id}/targets/${targetId}/retry`
        : `/api/publish-jobs/${job.id}/${action}`
      const updated = await postAPI<PublishJob>(path)
      activeJobIdRef.current = updated.id
      setJob(updated)
      await refreshProgress(updated.id)
      await loadJobHistory()
      setMessage(action === 'pause' ? 'Đã tạm dừng dry-run job.' : action === 'cancel' ? 'Đã hủy dry-run job.' : 'Đã đưa target thất bại vào hàng đợi retry.')
    } catch {
      setMessage(action === 'pause' ? 'Không tạm dừng được dry-run job.' : action === 'cancel' ? 'Không hủy được dry-run job.' : 'Không retry được target thất bại.')
    } finally {
      setJobActionPending(null)
    }
  }

  async function createFanpageChannel() {
    const displayName = newChannelName.trim()
    if (!displayName) {
      setMessage('Nhập tên Fanpage trước khi thêm kênh.')
      return
    }
    setCreatingChannel(true)
    try {
      const created = await postAPI<SocialChannel>('/api/channels', {
        platform: 'facebook',
        channel_type: 'fanpage',
        display_name: displayName,
        username: newChannelUsername.trim() || null,
      })
      const createdChannelFallback: ChannelSelectorItem = {
        ...created,
        live_guard_enabled: false,
        is_selectable: false,
        disabled_reason: 'selector_refresh_pending',
        supported_task_types: [],
      }
      setNewChannelName('')
      setNewChannelUsername('')
      setQuery('')
      setChannels(prev => [createdChannelFallback, ...prev.filter(channel => channel.id !== created.id)])
      setSelected(prev => prev.includes(created.id) ? prev : [...prev, created.id])
      await loadChannels('')
      setMessage(`Đã thêm Fanpage ${created.display_name}; selector sẽ hiển thị readiness từ backend.`)
    } catch {
      setMessage('Không tạo được Fanpage channel.')
    } finally {
      setCreatingChannel(false)
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
          <div style={{ display: 'grid', gridTemplateColumns: '1fr minmax(110px, 0.35fr)', gap: '8px' }}>
            <input value={mediaUrl} onChange={event => setMediaUrl(event.target.value)} placeholder="https://example.com/media.png" style={inputStyle()} />
            <input value={mediaMimeType} onChange={event => setMediaMimeType(event.target.value)} placeholder="image/png" style={inputStyle()} />
          </div>
          <button type="button" onClick={createMediaAsset} style={{ ...smallButtonStyle(), width: 'fit-content' }}>THÊM MEDIA ASSET</button>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {mediaAssets.map(asset => (
              <label key={asset.id} style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', color: 'var(--muted)' }}>
                <input type="checkbox" checked={selectedMediaIds.includes(asset.id)} onChange={() => toggleMediaAsset(asset.id)} />
                <span>{asset.type.toUpperCase()} · {asset.url ?? asset.local_ref ?? asset.id.slice(0, 8)}</span>
              </label>
            ))}
            {mediaAssets.length === 0 && <div style={{ fontSize: '11px', color: 'var(--muted)' }}>Chưa có media asset. Thêm URL để attach vào content.</div>}
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
          <button
            type="button"
            disabled
            style={{ ...buttonStyle('#64748b'), opacity: 0.65, cursor: 'not-allowed' }}
            title="Seeding & Push Feedback settings are coming soon. Not available in the Phase 1 dry-run pilot."
          >
            CÀI ĐẶT SEEDING / PUSH FEED BACK (COMING SOON)
          </button>
        </section>

        <section style={panelStyle()}>
          <SectionTitle title="Cột 3 — Chọn Fanpage đăng bài" />
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <button type="button" onClick={() => loadChannels()} style={smallButtonStyle()}><RefreshCw size={13} /> TẢI LẠI</button>
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
          {readinessDiagnostics.length > 0 && <ReadinessDiagnostics diagnostics={readinessDiagnostics} />}
          <div style={{ display: 'grid', gap: '8px', border: '1px solid var(--border)', borderRadius: '12px', padding: '10px', background: 'var(--surface)' }}>
            <div style={{ fontSize: '11px', color: 'var(--muted)', fontWeight: 800 }}>Thêm Fanpage cho dry-run</div>
            <input aria-label="Tên Fanpage mới" value={newChannelName} onChange={event => setNewChannelName(event.target.value)} placeholder="Tên Fanpage" style={inputStyle()} />
            <input aria-label="Username Fanpage mới" value={newChannelUsername} onChange={event => setNewChannelUsername(event.target.value)} placeholder="username tuỳ chọn" style={inputStyle()} />
            <button type="button" onClick={createFanpageChannel} disabled={creatingChannel} style={{ ...buttonStyle('#2563eb'), opacity: creatingChannel ? 0.7 : 1 }}>{creatingChannel ? 'ĐANG THÊM...' : '+ THÊM TRANG CẦN ĐĂNG'}</button>
          </div>
        </section>
      </div>

      <div style={{ position: 'sticky', bottom: 0, zIndex: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px', background: 'rgba(255,255,255,0.94)', border: '1px solid var(--border)', borderRadius: '14px', padding: '12px 14px', boxShadow: '0 10px 30px rgba(15,23,42,0.12)' }}>
        <div style={{ fontSize: '12px', color: 'var(--muted)' }}>
          Thời gian: {safeMinDelay}-{safeMaxDelay}s · Định dạng: {activeAttachment} · Media: {selectedMediaIds.length} · Fanpage: {selected.length} · Seeding: tắt · Ước tính: dry-run
        </div>
        <button type="button" onClick={startDryRunJob} disabled={submitting} style={buttonStyle('#16a34a')}>
          <Play size={15} /> {submitting ? 'ĐANG TẠO...' : 'BẮT ĐẦU ĐĂNG BÀI (DRY-RUN)'}
        </button>
      </div>

      <JobHistoryPanel jobs={jobHistory} loading={historyLoading} onRefresh={loadJobHistory} onOpen={openHistoryJob} />

      {job && <ProgressPreview job={job} progress={progress} channels={channels} actionPending={jobActionPending} onPause={() => runJobAction('pause')} onCancel={() => runJobAction('cancel')} onRetryTarget={targetId => runJobAction('retry', targetId)} />}
    </div>
  )
}

function ReadinessDiagnostics({ diagnostics }: { diagnostics: ReadinessDiagnostic[] }) {
  return (
    <div style={{ border: '1px solid rgba(217,119,6,0.35)', background: 'rgba(217,119,6,0.08)', borderRadius: '12px', padding: '10px', display: 'grid', gap: '6px' }}>
      <div style={{ fontSize: '11px', fontWeight: 850, color: 'var(--yellow)' }}>Diagnostics dry-run</div>
      {diagnostics.map(item => (
        <div key={item.key} style={{ display: 'grid', gap: '3px', fontSize: '11px', color: 'var(--muted)' }}>
          <strong style={{ color: 'var(--text)' }}>{item.title}: {item.detail}</strong>
          <span>Trạng thái: {item.status}</span>
        </div>
      ))}
      <div style={{ fontSize: '11px', color: 'var(--muted)' }}>Kiểm tra local agent online, capability publish-dry-run và Facebook profile khớp Fanpage.</div>
    </div>
  )
}

function JobHistoryPanel({ jobs, loading, onRefresh, onOpen }: { jobs: PublishJob[]; loading: boolean; onRefresh: () => void; onOpen: (job: PublishJob) => void }) {
  const [statusFilter, setStatusFilter] = useState('all')
  const filteredJobs = statusFilter === 'all' ? jobs : jobs.filter(item => item.status === statusFilter)
  return (
    <section style={panelStyle()}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
        <SectionTitle title="Lịch sử dry-run" />
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
          <label style={{ ...labelStyle(), display: 'flex', gap: '6px', alignItems: 'center' }}>
            Lọc lịch sử dry-run theo trạng thái
            <select aria-label="Lọc lịch sử dry-run theo trạng thái" value={statusFilter} onChange={event => setStatusFilter(event.target.value)} style={{ ...inputStyle(), width: '140px', padding: '7px 9px' }}>
              <option value="all">Tất cả</option>
              <option value="queued">Queued</option>
              <option value="dispatching">Dispatching</option>
              <option value="posted">Posted</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
              <option value="paused">Paused</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </label>
          <button type="button" onClick={onRefresh} style={smallButtonStyle()}><RefreshCw size={13} /> TẢI LẠI</button>
        </div>
      </div>
      {loading && <div style={{ fontSize: '12px', color: 'var(--muted)' }}>Đang tải lịch sử dry-run...</div>}
      {!loading && jobs.length === 0 && <div style={{ fontSize: '12px', color: 'var(--muted)' }}>Chưa có dry-run job gần đây.</div>}
      {!loading && jobs.length > 0 && filteredJobs.length === 0 && <div style={{ fontSize: '12px', color: 'var(--muted)' }}>Không có dry-run job ở trạng thái này.</div>}
      {!loading && filteredJobs.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {filteredJobs.map(item => (
            <div key={item.id} style={{ border: '1px solid var(--border)', borderRadius: '10px', padding: '10px', display: 'flex', justifyContent: 'space-between', gap: '10px', alignItems: 'center', flexWrap: 'wrap', background: 'var(--surface)' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <strong style={{ fontSize: '12px' }}>{item.id.slice(0, 8)}</strong>
                <span style={{ fontSize: '11px', color: 'var(--muted)' }}>{formatHistoryCreatedAt(item.created_at)}</span>
                <span style={progressStatusChipStyle(item.status)}>{item.status} · {item.targets.length} target</span>
              </div>
              <button type="button" onClick={() => onOpen(item)} style={smallButtonStyle()}>MỞ TIẾN TRÌNH</button>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

function formatHistoryCreatedAt(value: string) {
  const createdAt = new Date(value)
  if (!Number.isFinite(createdAt.getTime())) return 'Thời gian không hợp lệ'
  const pad = (part: number) => String(part).padStart(2, '0')
  return `${pad(createdAt.getUTCDate())}/${pad(createdAt.getUTCMonth() + 1)}/${createdAt.getUTCFullYear()}, ${pad(createdAt.getUTCHours())}:${pad(createdAt.getUTCMinutes())}`
}

function ProgressPreview({
  job,
  progress,
  channels,
  actionPending,
  onPause,
  onCancel,
  onRetryTarget,
}: {
  job: PublishJob
  progress: PublishJobProgress | null
  channels: ChannelSelectorItem[]
  actionPending: string | null
  onPause: () => void
  onCancel: () => void
  onRetryTarget: (targetId: string) => void
}) {
  const counts = progress?.counts
  const total = counts?.total ?? job.targets.length
  const queued = counts?.queued ?? job.targets.filter(target => ['queued', 'retry'].includes(target.status)).length
  const failed = counts?.failed ?? job.targets.filter(target => target.status === 'failed').length
  const posted = counts?.posted ?? job.targets.filter(target => target.status === 'posted').length
  const dispatching = counts?.dispatching ?? 0
  const percent = progress?.percent_complete ?? (total === 0 ? 0 : Math.round((posted + failed) * 100 / total))
  const safeEventMessage = safeProgressMessage(progress?.events[0]?.message ?? null)
  const channelById = new Map(channels.map(channel => [channel.id, channel]))
  const canPause = ['queued', 'dispatching'].includes(progress?.status ?? job.status)
  const canCancel = !isPublishTerminalStatus(progress?.status ?? job.status)
  const targetRows = progress?.targets ?? []
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
          {safeEventMessage && <div style={{ fontSize: '12px', color: 'var(--muted)' }}>{safeEventMessage}</div>}
          {progress && <TargetProgressDetails progress={progress} channelById={channelById} actionPending={actionPending} onRetryTarget={onRetryTarget} />}
          <div style={{ fontSize: '12px', color: 'var(--yellow)' }}>Đây là dry-run preview. Live posting vẫn cần Safety Gate và phê duyệt riêng.</div>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <button type="button" onClick={onPause} disabled={!canPause || actionPending !== null} style={{ ...smallButtonStyle(), width: 'fit-content', opacity: canPause && actionPending === null ? 1 : 0.55 }}>TẠM DỪNG</button>
            <button type="button" onClick={onCancel} disabled={!canCancel || actionPending !== null} style={{ ...smallButtonStyle(), width: 'fit-content', opacity: canCancel && actionPending === null ? 1 : 0.55 }}>HỦY JOB</button>
            {targetRows.some(target => target.status === 'failed') && <span style={{ fontSize: '11px', color: 'var(--muted)', alignSelf: 'center' }}>Retry từng target thất bại ở danh sách bên dưới.</span>}
          </div>
        </div>
      </div>
    </section>
  )
}

function safeExternalPostUrl(url: string | null) {
  if (!url) return null
  try {
    const parsed = new URL(url)
    return ['http:', 'https:'].includes(parsed.protocol) ? url : null
  } catch {
    return null
  }
}

function safeProgressMessage(message: string | null) {
  if (!message) return null
  const rawPatterns = [/traceback/i, /api \d{3}/i, /proxy/i, /stack/i]
  if (rawPatterns.some(pattern => pattern.test(message))) return 'Không tải được chi tiết tiến trình an toàn.'
  return message.length > 160 ? `${message.slice(0, 157)}...` : message
}

function safeTargetErrorMessage(message: string | null) {
  if (!message) return null
  const rawPatterns = [/traceback/i, /api \d{3}/i, /proxy/i, /stack/i]
  if (rawPatterns.some(pattern => pattern.test(message))) return 'Không đăng được target này. Xem mã lỗi để xử lý.'
  return message.length > 160 ? `${message.slice(0, 157)}...` : message
}

function progressStatusLabel(status: string) {
  if (status === 'posted') return 'Đã mô phỏng'
  if (status === 'failed') return 'Thất bại'
  if (status === 'dispatching') return 'Đang xử lý'
  if (status === 'cancelled') return 'Đã hủy'
  return 'Đang chờ'
}

function progressStatusChipStyle(status: string): React.CSSProperties {
  const color = status === 'posted' ? 'var(--green)' : status === 'failed' ? 'var(--red)' : status === 'dispatching' ? 'var(--yellow)' : 'var(--muted)'
  return { ...chipStyle(), color, borderColor: color }
}

function targetReadinessHint(errorCode: string | null, errorMessage: string | null) {
  if (errorCode === 'agent_not_ready' || errorMessage === 'No ready agent session for channel') return 'Kiểm tra Agent đang online, có capability publish-dry-run và Facebook profile khớp Fanpage.'
  return null
}

function TargetProgressDetails({
  progress,
  channelById,
  actionPending,
  onRetryTarget,
}: {
  progress: PublishJobProgress
  channelById: Map<string, ChannelSelectorItem>
  actionPending: string | null
  onRetryTarget: (targetId: string) => void
}) {
  const failedTargets = progress.targets.filter(target => target.status === 'failed').length
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
        <div style={{ fontSize: '12px', fontWeight: 850 }}>Chi tiết target</div>
        {failedTargets > 0 && <span style={{ ...chipStyle(), color: 'var(--red)', borderColor: 'var(--red)' }}>Target thất bại: {failedTargets}</span>}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        {progress.targets.map(target => {
          const channel = channelById.get(target.channel_id)
          const channelName = channel?.display_name ?? target.channel_id
          const channelSafeId = channel ? (channel.safe_display_id ?? 'ID an toàn chưa có') : target.channel_id
          const safeUrl = safeExternalPostUrl(target.external_post_url)
          const safeErrorMessage = safeTargetErrorMessage(target.error_message)
          const readinessHint = targetReadinessHint(target.error_code, target.error_message)
          return (
            <div key={target.id} style={{ border: '1px solid var(--border)', borderRadius: '10px', padding: '10px', display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '11px', background: 'var(--surface)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', flexWrap: 'wrap' }}>
                <strong>{target.id}</strong>
                <span style={progressStatusChipStyle(target.status)}>{progressStatusLabel(target.status)}</span>
              </div>
              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', color: 'var(--muted)' }}>
                <span>{channelName}</span>
                <span>{channelSafeId}</span>
              </div>
              <div>Số lần thử: {target.attempts}</div>
              {safeUrl && <a href={safeUrl} target="_blank" rel="noreferrer" style={{ color: 'var(--accent)', overflowWrap: 'anywhere' }}>{safeUrl}</a>}
              {target.external_post_url && !safeUrl && <div style={{ color: 'var(--muted)' }}>URL không hợp lệ</div>}
              {target.error_code && <div style={{ color: 'var(--red)', fontWeight: 800 }}>{target.error_code}</div>}
              {readinessHint && <div style={{ color: 'var(--yellow)', overflowWrap: 'anywhere' }}>{readinessHint}</div>}
              {safeErrorMessage && <div style={{ color: 'var(--red)', overflowWrap: 'anywhere' }}>{safeErrorMessage}</div>}
              {target.status === 'failed' && progress.status !== 'paused' && (
                <button type="button" onClick={() => onRetryTarget(target.id)} disabled={actionPending !== null} style={{ ...smallButtonStyle(), width: 'fit-content', opacity: actionPending === null ? 1 : 0.55 }}>
                  {actionPending === `retry:${target.id}` ? 'ĐANG RETRY...' : 'RETRY TARGET'}
                </button>
              )}
              {target.status === 'failed' && progress.status === 'paused' && <div style={{ color: 'var(--muted)' }}>Job đang tạm dừng; hủy hoặc mở job khác trước khi retry.</div>}
            </div>
          )
        })}
      </div>
    </div>
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
