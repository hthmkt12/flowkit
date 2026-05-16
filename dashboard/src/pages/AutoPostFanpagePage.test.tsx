import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import AutoPostFanpagePage from './AutoPostFanpagePage'

type FetchCall = { url: string; init?: RequestInit }

const selectorResponse = {
  items: [
    {
      id: 'channel-1',
      platform: 'facebook',
      channel_type: 'fanpage',
      display_name: 'ZooPost Fanpage',
      username: 'zoo-page',
      safe_display_id: 'fanpage-channel',
      connection_status: 'ready',
      live_guard_enabled: false,
      is_selectable: true,
      disabled_reason: null,
      supported_task_types: ['facebook.post_text'],
    },
    {
      id: 'channel-2',
      platform: 'facebook',
      channel_type: 'fanpage',
      display_name: 'Backup Fanpage',
      username: 'backup-page',
      safe_display_id: 'fanpage-backup',
      connection_status: 'ready',
      live_guard_enabled: false,
      is_selectable: true,
      disabled_reason: null,
      supported_task_types: ['facebook.post_text'],
    },
  ],
  limit: 100,
}

function jsonResponse(body: unknown) {
  return Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response)
}

function deferredResponse(body?: unknown) {
  let resolve!: (nextBody?: unknown) => void
  const pending = new Promise<Response>(promiseResolve => {
    resolve = nextBody => promiseResolve({ ok: true, json: () => Promise.resolve(nextBody ?? body) } as Response)
  })
  return { pending, resolve }
}

function progressPayload(jobId: string, status: string, percentComplete: number, message: string) {
  return {
    job_id: jobId,
    status,
    counts: {
      total: 1,
      queued: status === 'queued' ? 1 : 0,
      dispatching: status === 'dispatching' ? 1 : 0,
      posted: status === 'posted' ? 1 : 0,
      failed: status === 'failed' ? 1 : 0,
      cancelled: status === 'cancelled' ? 1 : 0,
    },
    percent_complete: percentComplete,
    targets: [{ id: 'target-1', channel_id: 'channel-1', status, attempts: 0, external_post_id: null, external_post_url: null, error_code: null, error_message: null }],
    events: [{ id: `event-${jobId}-${status}`, type: `job.${status}`, severity: 'info', message, target_id: null, data: {} }],
  }
}

function jobProgressPayload(status: string, percentComplete: number, message: string) {
  return progressPayload('job-1', status, percentComplete, message)
}

describe('AutoPostFanpagePage', () => {
  const calls: FetchCall[] = []

  beforeEach(() => {
    calls.length = 0
    vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
      calls.push({ url, init })
      if (url.startsWith('/api/channels/selector')) return jsonResponse(selectorResponse)
      if (url === '/api/media-assets' && init?.method === 'POST') return jsonResponse({ id: 'media-new', type: 'image', source: 'external_url', url: 'https://example.com/new.png', local_ref: null, size_bytes: null, mime_type: 'image/jpeg', metadata: {} })
      if (url === '/api/media-assets') return jsonResponse([{ id: 'media-1', type: 'image', source: 'external_url', url: 'https://example.com/a.png', local_ref: null, size_bytes: 123, mime_type: 'image/png', metadata: {} }])
      if (url === '/api/content-items') return jsonResponse({ id: 'content-1', title: 'ZooPost dry-run', body: 'Xin chào [r]', syntax_mode: 'zoopost', status: 'draft' })
      if (url === '/api/content-items/content-1/preview?seed=channel-1&channel_id=channel-1') return jsonResponse({ content_id: 'content-1', channel_id: 'channel-1', body: 'Xin chào 😄', syntax_mode: 'zoopost', seed: 'channel-1', attachments: [], warnings: [] })
      if (url === '/api/publish-jobs' && init?.method === 'POST') return jsonResponse({ id: 'job-1', status: 'queued', dry_run: true, created_at: '2026-05-16T10:30:00Z', targets: [{ id: 'target-1', channel_id: 'channel-1', status: 'queued' }] })
      if (url === '/api/publish-jobs?limit=5') return jsonResponse([])
      if (url === '/api/publish-jobs/job-1/progress') return jsonResponse(jobProgressPayload('queued', 0, 'Publish job queued'))
      return Promise.resolve({ ok: false, status: 404, text: () => Promise.resolve(`missing mock ${url}`) } as Response)
    }))
  })

  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it('loads selector channels and creates a saved preview', async () => {
    render(<AutoPostFanpagePage />)

    expect(await screen.findByText('ZooPost Fanpage')).toBeTruthy()
    expect(calls[0].url).toBe('/api/channels/selector?platform=facebook&channel_type=fanpage&limit=100')

    fireEvent.click(screen.getByLabelText(/ZooPost Fanpage/))
    await act(async () => {
      fireEvent.click(screen.getByText('Xem preview cú pháp'))
    })

    await waitFor(() => expect(screen.getByText('Xin chào 😄')).toBeTruthy())
    expect(calls.some(call => call.url === '/api/content-items')).toBe(true)
    expect(calls.some(call => call.url === '/api/content-items/content-1/preview?seed=channel-1&channel_id=channel-1')).toBe(true)
  })

  it('loads recent dry-run jobs and reopens progress details', async () => {
    const historyJob = { id: 'job-history', status: 'failed', dry_run: true, created_at: '2026-05-16T10:30:00Z', targets: [{ id: 'target-history', channel_id: 'channel-1', status: 'failed' }] }
    vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
      calls.push({ url, init })
      if (url.startsWith('/api/channels/selector')) return jsonResponse(selectorResponse)
      if (url === '/api/media-assets') return jsonResponse([])
      if (url === '/api/publish-jobs?limit=5') return jsonResponse([historyJob])
      if (url === '/api/publish-jobs/job-history/progress') return jsonResponse({
        job_id: 'job-history',
        status: 'failed',
        counts: { total: 1, queued: 0, dispatching: 0, posted: 0, failed: 1, cancelled: 0 },
        percent_complete: 100,
        targets: [{ id: 'target-history', channel_id: 'channel-1', status: 'failed', attempts: 2, external_post_id: null, external_post_url: null, error_code: 'HISTORY_FAILED', error_message: 'History dry-run failed' }],
        events: [{ id: 'event-history', type: 'job.failed', severity: 'error', message: 'History target failed', target_id: 'target-history', data: {} }],
      })
      return Promise.resolve({ ok: false, status: 404, text: () => Promise.resolve(`missing mock ${url}`) } as Response)
    }))

    render(<AutoPostFanpagePage />)

    expect(await screen.findByText('Lịch sử dry-run')).toBeTruthy()
    expect(calls.some(call => call.url === '/api/publish-jobs?limit=5')).toBe(true)
    expect(screen.getByText('job-hist')).toBeTruthy()
    expect(screen.getByText('16/05/2026, 10:30')).toBeTruthy()
    expect(screen.getByText('failed · 1 target')).toBeTruthy()
    await act(async () => {
      fireEvent.click(screen.getByText('MỞ TIẾN TRÌNH'))
    })

    await waitFor(() => expect(screen.getByText('target-history')).toBeTruthy())
    expect(screen.getByText('HISTORY_FAILED')).toBeTruthy()
    expect(calls.some(call => call.url === '/api/publish-jobs/job-history/progress')).toBe(true)
  })

  it('filters dry-run history by status', async () => {
    const historyJobs = [
      { id: 'job-queued', status: 'queued', dry_run: true, created_at: '2026-05-16T10:30:00Z', targets: [{ id: 'target-queued', channel_id: 'channel-1', status: 'queued' }] },
      { id: 'job-failed', status: 'failed', dry_run: true, created_at: '2026-05-16T10:31:00Z', targets: [{ id: 'target-failed', channel_id: 'channel-1', status: 'failed' }] },
      { id: 'job-posted', status: 'posted', dry_run: true, created_at: '2026-05-16T10:32:00Z', targets: [{ id: 'target-posted', channel_id: 'channel-1', status: 'posted' }] },
    ]
    vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
      calls.push({ url, init })
      if (url.startsWith('/api/channels/selector')) return jsonResponse(selectorResponse)
      if (url === '/api/media-assets') return jsonResponse([])
      if (url === '/api/publish-jobs?limit=5') return jsonResponse(historyJobs)
      return Promise.resolve({ ok: false, status: 404, text: () => Promise.resolve(`missing mock ${url}`) } as Response)
    }))

    render(<AutoPostFanpagePage />)

    expect(await screen.findByText('job-queu')).toBeTruthy()
    expect(screen.getByText('job-fail')).toBeTruthy()
    expect(screen.getByText('job-post')).toBeTruthy()

    fireEvent.change(screen.getByLabelText('Lọc lịch sử dry-run theo trạng thái'), { target: { value: 'failed' } })

    expect(screen.queryByText('job-queu')).toBeNull()
    expect(screen.getByText('job-fail')).toBeTruthy()
    expect(screen.queryByText('job-post')).toBeNull()
    expect(screen.getByText('failed · 1 target')).toBeTruthy()
  })

  it('shows an empty state when the selected history status has no jobs', async () => {
    const historyJobs = [
      { id: 'job-queued', status: 'queued', dry_run: true, created_at: '2026-05-16T10:30:00Z', targets: [{ id: 'target-queued', channel_id: 'channel-1', status: 'queued' }] },
    ]
    vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
      calls.push({ url, init })
      if (url.startsWith('/api/channels/selector')) return jsonResponse(selectorResponse)
      if (url === '/api/media-assets') return jsonResponse([])
      if (url === '/api/publish-jobs?limit=5') return jsonResponse(historyJobs)
      return Promise.resolve({ ok: false, status: 404, text: () => Promise.resolve(`missing mock ${url}`) } as Response)
    }))

    render(<AutoPostFanpagePage />)

    expect(await screen.findByText('job-queu')).toBeTruthy()

    fireEvent.change(screen.getByLabelText('Lọc lịch sử dry-run theo trạng thái'), { target: { value: 'failed' } })

    expect(screen.getByText('Không có dry-run job ở trạng thái này.')).toBeTruthy()
    expect(screen.queryByText('job-queu')).toBeNull()
  })

  it('creates a dry-run job and renders backend progress', async () => {
    render(<AutoPostFanpagePage />)

    expect(await screen.findByText('ZooPost Fanpage')).toBeTruthy()
    fireEvent.click(screen.getByLabelText(/ZooPost Fanpage/))
    await act(async () => {
      fireEvent.click(screen.getByText('BẮT ĐẦU ĐĂNG BÀI (DRY-RUN)'))
    })

    await waitFor(() => expect(screen.getByText(/Đã tạo dry-run job/)).toBeTruthy())
    expect(screen.getByText('Publish job queued')).toBeTruthy()
    expect(screen.getByText('0%')).toBeTruthy()
    expect(calls.some(call => call.url === '/api/publish-jobs/job-1/progress')).toBe(true)

    const publishCall = calls.find(call => call.url === '/api/publish-jobs' && call.init?.method === 'POST')
    expect(publishCall?.init?.method).toBe('POST')
    expect(JSON.parse(String(publishCall?.init?.body))).toMatchObject({
      content_item_id: 'content-1',
      channel_ids: ['channel-1'],
      dry_run: true,
      delay_policy: { min_delay_seconds: 60, max_delay_seconds: 180 },
    })
  })

  it('includes selected media assets when saving content', async () => {
    render(<AutoPostFanpagePage />)

    expect(await screen.findByText('ZooPost Fanpage')).toBeTruthy()
    expect(await screen.findByText(/https:\/\/example.com\/a.png/)).toBeTruthy()
    fireEvent.click(screen.getByLabelText(/https:\/\/example.com\/a.png/))
    fireEvent.click(screen.getByLabelText(/ZooPost Fanpage/))
    await act(async () => {
      fireEvent.click(screen.getByText('BẮT ĐẦU ĐĂNG BÀI (DRY-RUN)'))
    })

    await waitFor(() => expect(screen.getByText(/Đã tạo dry-run job/)).toBeTruthy())
    const contentCall = calls.find(call => call.url === '/api/content-items')
    expect(JSON.parse(String(contentCall?.init?.body))).toMatchObject({
      media_asset_ids: ['media-1'],
    })
  })

  it('creates a media asset from URL fields and selects it for content save', async () => {
    render(<AutoPostFanpagePage />)

    expect(await screen.findByText('ZooPost Fanpage')).toBeTruthy()
    fireEvent.change(screen.getByPlaceholderText('https://example.com/media.png'), { target: { value: 'https://example.com/new.png' } })
    fireEvent.change(screen.getByPlaceholderText('image/png'), { target: { value: 'image/jpeg' } })

    await act(async () => {
      fireEvent.click(screen.getByText('THÊM MEDIA ASSET'))
    })

    await waitFor(() => expect(screen.getByText(/Đã thêm media asset/)).toBeTruthy())
    expect(screen.getByLabelText(/https:\/\/example.com\/new.png/)).toBeTruthy()

    fireEvent.click(screen.getByLabelText(/ZooPost Fanpage/))
    await act(async () => {
      fireEvent.click(screen.getByText('BẮT ĐẦU ĐĂNG BÀI (DRY-RUN)'))
    })

    await waitFor(() => expect(screen.getByText(/Đã tạo dry-run job/)).toBeTruthy())
    const mediaCreateCall = calls.find(call => call.url === '/api/media-assets' && call.init?.method === 'POST')
    expect(JSON.parse(String(mediaCreateCall?.init?.body))).toMatchObject({
      type: 'image',
      source: 'external_url',
      url: 'https://example.com/new.png',
      mime_type: 'image/jpeg',
    })
    const contentCall = calls.find(call => call.url === '/api/content-items')
    expect(JSON.parse(String(contentCall?.init?.body))).toMatchObject({
      media_asset_ids: ['media-new'],
    })
  })

  it('renders per-target progress details', async () => {
    const detailedProgress = {
      job_id: 'job-1',
      status: 'failed',
      counts: { total: 2, queued: 0, dispatching: 0, posted: 1, failed: 1, cancelled: 0 },
      percent_complete: 100,
      targets: [
        { id: 'target-1', channel_id: 'channel-1', status: 'posted', attempts: 1, external_post_id: 'post-1', external_post_url: 'https://facebook.example/posts/1', error_code: null, error_message: null },
        { id: 'target-2', channel_id: 'channel-2', status: 'failed', attempts: 2, external_post_id: null, external_post_url: null, error_code: 'POST_FAILED', error_message: 'Dry-run validation failed' },
      ],
      events: [{ id: 'event-failed', type: 'job.failed', severity: 'error', message: 'One target failed', target_id: 'target-2', data: {} }],
    }
    vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
      calls.push({ url, init })
      if (url.startsWith('/api/channels/selector')) return jsonResponse(selectorResponse)
      if (url === '/api/media-assets') return jsonResponse([])
      if (url === '/api/content-items') return jsonResponse({ id: 'content-1', title: 'ZooPost dry-run', body: 'Xin chào [r]', syntax_mode: 'zoopost', status: 'draft' })
      if (url === '/api/publish-jobs' && init?.method === 'POST') return jsonResponse({ id: 'job-1', status: 'queued', dry_run: true, created_at: '2026-05-16T10:30:00Z', targets: [{ id: 'target-1', channel_id: 'channel-1', status: 'queued' }, { id: 'target-2', channel_id: 'channel-2', status: 'queued' }] })
      if (url === '/api/publish-jobs?limit=5') return jsonResponse([])
      if (url === '/api/publish-jobs/job-1/progress') return jsonResponse(detailedProgress)
      return Promise.resolve({ ok: false, status: 404, text: () => Promise.resolve(`missing mock ${url}`) } as Response)
    }))

    render(<AutoPostFanpagePage />)

    expect(await screen.findByText('ZooPost Fanpage')).toBeTruthy()
    fireEvent.click(screen.getByLabelText(/ZooPost Fanpage/))
    await act(async () => {
      fireEvent.click(screen.getByText('BẮT ĐẦU ĐĂNG BÀI (DRY-RUN)'))
    })

    await waitFor(() => expect(screen.getByText('Chi tiết target')).toBeTruthy())
    expect(screen.getByText('Target thất bại: 1')).toBeTruthy()
    expect(screen.getByText('target-1')).toBeTruthy()
    expect(screen.getAllByText('ZooPost Fanpage').length).toBeGreaterThan(0)
    expect(screen.getByText('fanpage-channel')).toBeTruthy()
    expect(screen.getByText('Đã mô phỏng')).toBeTruthy()
    expect(screen.getByText('Số lần thử: 1')).toBeTruthy()
    expect(screen.getByText('https://facebook.example/posts/1')).toBeTruthy()
    expect(screen.getByText('target-2')).toBeTruthy()
    expect(screen.getAllByText('Backup Fanpage').length).toBeGreaterThan(0)
    expect(screen.getByText('fanpage-backup')).toBeTruthy()
    expect(screen.getAllByText('Thất bại').length).toBeGreaterThan(0)
    expect(screen.getByText('Số lần thử: 2')).toBeTruthy()
    expect(screen.getByText('POST_FAILED')).toBeTruthy()
    expect(screen.getByText('Dry-run validation failed')).toBeTruthy()
  })

  it('does not expose channel ids when selector metadata lacks a safe display id', async () => {
    const selectorWithNullSafeId = {
      items: [{ ...selectorResponse.items[0], id: 'channel-null-safe', display_name: 'Null Safe Fanpage', safe_display_id: null }],
      limit: 100,
    }
    const detailedProgress = {
      job_id: 'job-1',
      status: 'posted',
      counts: { total: 1, queued: 0, dispatching: 0, posted: 1, failed: 0, cancelled: 0 },
      percent_complete: 100,
      targets: [
        { id: 'target-null-safe', channel_id: 'channel-null-safe', status: 'posted', attempts: 1, external_post_id: null, external_post_url: null, error_code: null, error_message: null },
      ],
      events: [{ id: 'event-posted', type: 'job.posted', severity: 'info', message: 'Dry-run target complete', target_id: 'target-null-safe', data: {} }],
    }
    vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
      calls.push({ url, init })
      if (url.startsWith('/api/channels/selector')) return jsonResponse(selectorWithNullSafeId)
      if (url === '/api/media-assets') return jsonResponse([])
      if (url === '/api/content-items') return jsonResponse({ id: 'content-1', title: 'ZooPost dry-run', body: 'Xin chào [r]', syntax_mode: 'zoopost', status: 'draft' })
      if (url === '/api/publish-jobs' && init?.method === 'POST') return jsonResponse({ id: 'job-1', status: 'queued', dry_run: true, created_at: '2026-05-16T10:30:00Z', targets: [{ id: 'target-null-safe', channel_id: 'channel-null-safe', status: 'queued' }] })
      if (url === '/api/publish-jobs?limit=5') return jsonResponse([])
      if (url === '/api/publish-jobs/job-1/progress') return jsonResponse(detailedProgress)
      return Promise.resolve({ ok: false, status: 404, text: () => Promise.resolve(`missing mock ${url}`) } as Response)
    }))

    render(<AutoPostFanpagePage />)

    expect(await screen.findByText('Null Safe Fanpage')).toBeTruthy()
    fireEvent.click(screen.getByLabelText(/Null Safe Fanpage/))
    await act(async () => {
      fireEvent.click(screen.getByText('BẮT ĐẦU ĐĂNG BÀI (DRY-RUN)'))
    })

    await waitFor(() => expect(screen.getByText('target-null-safe')).toBeTruthy())
    expect(screen.getAllByText('Null Safe Fanpage').length).toBeGreaterThan(0)
    expect(screen.getByText('ID an toàn chưa có')).toBeTruthy()
    expect(screen.queryByText('channel-null-safe')).toBeNull()
  })

  it('falls back to channel ids and labels non-final target statuses', async () => {
    const detailedProgress = {
      job_id: 'job-1',
      status: 'dispatching',
      counts: { total: 4, queued: 1, dispatching: 1, posted: 0, failed: 0, cancelled: 1 },
      percent_complete: 50,
      targets: [
        { id: 'target-dispatching', channel_id: 'unknown-dispatching', status: 'dispatching', attempts: 1, external_post_id: null, external_post_url: null, error_code: null, error_message: null },
        { id: 'target-cancelled', channel_id: 'unknown-cancelled', status: 'cancelled', attempts: 0, external_post_id: null, external_post_url: null, error_code: null, error_message: null },
        { id: 'target-retry', channel_id: 'unknown-retry', status: 'retry', attempts: 2, external_post_id: null, external_post_url: null, error_code: null, error_message: null },
      ],
      events: [{ id: 'event-progress', type: 'job.dispatching', severity: 'info', message: 'Dispatching targets', target_id: null, data: {} }],
    }
    vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
      calls.push({ url, init })
      if (url.startsWith('/api/channels/selector')) return jsonResponse(selectorResponse)
      if (url === '/api/media-assets') return jsonResponse([])
      if (url === '/api/content-items') return jsonResponse({ id: 'content-1', title: 'ZooPost dry-run', body: 'Xin chào [r]', syntax_mode: 'zoopost', status: 'draft' })
      if (url === '/api/publish-jobs' && init?.method === 'POST') return jsonResponse({ id: 'job-1', status: 'queued', dry_run: true, created_at: '2026-05-16T10:30:00Z', targets: [{ id: 'target-dispatching', channel_id: 'unknown-dispatching', status: 'queued' }] })
      if (url === '/api/publish-jobs?limit=5') return jsonResponse([])
      if (url === '/api/publish-jobs/job-1/progress') return jsonResponse(detailedProgress)
      return Promise.resolve({ ok: false, status: 404, text: () => Promise.resolve(`missing mock ${url}`) } as Response)
    }))

    render(<AutoPostFanpagePage />)

    expect(await screen.findByText('ZooPost Fanpage')).toBeTruthy()
    fireEvent.click(screen.getByLabelText(/ZooPost Fanpage/))
    await act(async () => {
      fireEvent.click(screen.getByText('BẮT ĐẦU ĐĂNG BÀI (DRY-RUN)'))
    })

    await waitFor(() => expect(screen.getByText('target-dispatching')).toBeTruthy())
    expect(screen.getAllByText('unknown-dispatching')).toHaveLength(2)
    expect(screen.getAllByText('unknown-cancelled')).toHaveLength(2)
    expect(screen.getAllByText('unknown-retry')).toHaveLength(2)
    expect(screen.getAllByText('Đang xử lý').length).toBeGreaterThan(0)
    expect(screen.getByText('Đã hủy')).toBeTruthy()
    expect(screen.getAllByText('Đang chờ').length).toBeGreaterThan(0)
  })

  it('renders unsafe target URLs and raw-looking errors safely', async () => {
    const unsafeProgress = {
      job_id: 'job-1',
      status: 'failed',
      counts: { total: 1, queued: 0, dispatching: 0, posted: 0, failed: 1, cancelled: 0 },
      percent_complete: 100,
      targets: [
        { id: 'target-unsafe', channel_id: 'channel-1', status: 'failed', attempts: 1, external_post_id: null, external_post_url: 'javascript:alert(1)', error_code: 'PROXY_FAILURE', error_message: 'API 500: proxy stack trace leaked' },
      ],
      events: [{ id: 'event-failed', type: 'job.failed', severity: 'error', message: 'API 500: proxy stack trace leaked', target_id: 'target-unsafe', data: {} }],
    }
    vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
      calls.push({ url, init })
      if (url.startsWith('/api/channels/selector')) return jsonResponse(selectorResponse)
      if (url === '/api/media-assets') return jsonResponse([])
      if (url === '/api/content-items') return jsonResponse({ id: 'content-1', title: 'ZooPost dry-run', body: 'Xin chào [r]', syntax_mode: 'zoopost', status: 'draft' })
      if (url === '/api/publish-jobs' && init?.method === 'POST') return jsonResponse({ id: 'job-1', status: 'queued', dry_run: true, created_at: '2026-05-16T10:30:00Z', targets: [{ id: 'target-unsafe', channel_id: 'channel-1', status: 'queued' }] })
      if (url === '/api/publish-jobs?limit=5') return jsonResponse([])
      if (url === '/api/publish-jobs/job-1/progress') return jsonResponse(unsafeProgress)
      return Promise.resolve({ ok: false, status: 404, text: () => Promise.resolve(`missing mock ${url}`) } as Response)
    }))

    render(<AutoPostFanpagePage />)

    expect(await screen.findByText('ZooPost Fanpage')).toBeTruthy()
    fireEvent.click(screen.getByLabelText(/ZooPost Fanpage/))
    await act(async () => {
      fireEvent.click(screen.getByText('BẮT ĐẦU ĐĂNG BÀI (DRY-RUN)'))
    })

    await waitFor(() => expect(screen.getByText('target-unsafe')).toBeTruthy())
    expect(screen.getByText('URL không hợp lệ')).toBeTruthy()
    expect(screen.queryByText('javascript:alert(1)')).toBeNull()
    expect(screen.getByText('PROXY_FAILURE')).toBeTruthy()
    expect(screen.getByText('Không đăng được target này. Xem mã lỗi để xử lý.')).toBeTruthy()
    expect(screen.getByText('Không tải được chi tiết tiến trình an toàn.')).toBeTruthy()
    expect(screen.queryByText('API 500: proxy stack trace leaked')).toBeNull()
  })

  it('polls publish progress until a terminal status is reached', async () => {
    vi.useFakeTimers()
    const progressResponses = [
      jobProgressPayload('queued', 0, 'Publish job queued'),
      jobProgressPayload('dispatching', 50, 'Dispatching dry-run target'),
      jobProgressPayload('posted', 100, 'Dry-run target complete'),
    ]
    vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
      calls.push({ url, init })
      if (url.startsWith('/api/channels/selector')) return jsonResponse(selectorResponse)
      if (url === '/api/media-assets') return jsonResponse([])
      if (url === '/api/content-items') return jsonResponse({ id: 'content-1', title: 'ZooPost dry-run', body: 'Xin chào [r]', syntax_mode: 'zoopost', status: 'draft' })
      if (url === '/api/publish-jobs' && init?.method === 'POST') return jsonResponse({ id: 'job-1', status: 'queued', dry_run: true, created_at: '2026-05-16T10:30:00Z', targets: [{ id: 'target-1', channel_id: 'channel-1', status: 'queued' }] })
      if (url === '/api/publish-jobs?limit=5') return jsonResponse([])
      if (url === '/api/publish-jobs/job-1/progress') return jsonResponse(progressResponses.shift() ?? jobProgressPayload('posted', 100, 'Dry-run target complete'))
      return Promise.resolve({ ok: false, status: 404, text: () => Promise.resolve(`missing mock ${url}`) } as Response)
    }))

    try {
      render(<AutoPostFanpagePage />)
      await act(async () => {
        await Promise.resolve()
        await Promise.resolve()
      })

      expect(screen.getByText('ZooPost Fanpage')).toBeTruthy()
      fireEvent.click(screen.getByLabelText(/ZooPost Fanpage/))
      await act(async () => {
        fireEvent.click(screen.getByText('BẮT ĐẦU ĐĂNG BÀI (DRY-RUN)'))
        await Promise.resolve()
        await Promise.resolve()
        await Promise.resolve()
      })

      expect(screen.getByText('Publish job queued')).toBeTruthy()
      expect(calls.filter(call => call.url === '/api/publish-jobs/job-1/progress')).toHaveLength(1)

      await act(async () => {
        vi.advanceTimersByTime(3000)
        await Promise.resolve()
      })
      expect(screen.getByText('Dispatching dry-run target')).toBeTruthy()
      expect(screen.getByText('50%')).toBeTruthy()
      expect(calls.filter(call => call.url === '/api/publish-jobs/job-1/progress')).toHaveLength(2)

      await act(async () => {
        vi.advanceTimersByTime(3000)
        await Promise.resolve()
      })
      expect(screen.getByText('Dry-run target complete')).toBeTruthy()
      expect(screen.getByText('100%')).toBeTruthy()
      expect(calls.filter(call => call.url === '/api/publish-jobs/job-1/progress')).toHaveLength(3)

      await act(async () => {
        vi.advanceTimersByTime(9000)
        await Promise.resolve()
      })
      expect(calls.filter(call => call.url === '/api/publish-jobs/job-1/progress')).toHaveLength(3)
    } finally {
      vi.useRealTimers()
    }
  })

  it('continues polling when non-terminal status repeats', async () => {
    vi.useFakeTimers()
    const progressResponses = [
      jobProgressPayload('queued', 0, 'Publish job queued'),
      jobProgressPayload('queued', 0, 'Publish job still queued'),
      jobProgressPayload('posted', 100, 'Dry-run target complete'),
    ]
    vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
      calls.push({ url, init })
      if (url.startsWith('/api/channels/selector')) return jsonResponse(selectorResponse)
      if (url === '/api/media-assets') return jsonResponse([])
      if (url === '/api/content-items') return jsonResponse({ id: 'content-1', title: 'ZooPost dry-run', body: 'Xin chào [r]', syntax_mode: 'zoopost', status: 'draft' })
      if (url === '/api/publish-jobs' && init?.method === 'POST') return jsonResponse({ id: 'job-1', status: 'queued', dry_run: true, created_at: '2026-05-16T10:30:00Z', targets: [{ id: 'target-1', channel_id: 'channel-1', status: 'queued' }] })
      if (url === '/api/publish-jobs?limit=5') return jsonResponse([])
      if (url === '/api/publish-jobs/job-1/progress') return jsonResponse(progressResponses.shift() ?? jobProgressPayload('posted', 100, 'Dry-run target complete'))
      return Promise.resolve({ ok: false, status: 404, text: () => Promise.resolve(`missing mock ${url}`) } as Response)
    }))

    try {
      render(<AutoPostFanpagePage />)
      await act(async () => {
        await Promise.resolve()
        await Promise.resolve()
      })

      fireEvent.click(screen.getByLabelText(/ZooPost Fanpage/))
      await act(async () => {
        fireEvent.click(screen.getByText('BẮT ĐẦU ĐĂNG BÀI (DRY-RUN)'))
        await Promise.resolve()
        await Promise.resolve()
        await Promise.resolve()
      })
      expect(screen.getByText('Publish job queued')).toBeTruthy()

      await act(async () => {
        vi.advanceTimersByTime(3000)
        await Promise.resolve()
        await Promise.resolve()
      })
      expect(screen.getByText('Publish job still queued')).toBeTruthy()
      expect(calls.filter(call => call.url === '/api/publish-jobs/job-1/progress')).toHaveLength(2)

      await act(async () => {
        vi.advanceTimersByTime(3000)
        await Promise.resolve()
        await Promise.resolve()
      })
      expect(screen.getByText('Dry-run target complete')).toBeTruthy()
      expect(calls.filter(call => call.url === '/api/publish-jobs/job-1/progress')).toHaveLength(3)
    } finally {
      vi.useRealTimers()
    }
  })

  it('continues polling after a transient progress fetch error', async () => {
    vi.useFakeTimers()
    let progressCallCount = 0
    vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
      calls.push({ url, init })
      if (url.startsWith('/api/channels/selector')) return jsonResponse(selectorResponse)
      if (url === '/api/media-assets') return jsonResponse([])
      if (url === '/api/content-items') return jsonResponse({ id: 'content-1', title: 'ZooPost dry-run', body: 'Xin chào [r]', syntax_mode: 'zoopost', status: 'draft' })
      if (url === '/api/publish-jobs' && init?.method === 'POST') return jsonResponse({ id: 'job-1', status: 'queued', dry_run: true, created_at: '2026-05-16T10:30:00Z', targets: [{ id: 'target-1', channel_id: 'channel-1', status: 'queued' }] })
      if (url === '/api/publish-jobs?limit=5') return jsonResponse([])
      if (url === '/api/publish-jobs/job-1/progress') {
        progressCallCount += 1
        if (progressCallCount === 2) return Promise.reject(new Error('temporary network error'))
        return jsonResponse(progressCallCount === 1
          ? jobProgressPayload('queued', 0, 'Publish job queued')
          : jobProgressPayload('posted', 100, 'Dry-run target complete'))
      }
      return Promise.resolve({ ok: false, status: 404, text: () => Promise.resolve(`missing mock ${url}`) } as Response)
    }))

    try {
      render(<AutoPostFanpagePage />)
      await act(async () => {
        await Promise.resolve()
        await Promise.resolve()
      })

      fireEvent.click(screen.getByLabelText(/ZooPost Fanpage/))
      await act(async () => {
        fireEvent.click(screen.getByText('BẮT ĐẦU ĐĂNG BÀI (DRY-RUN)'))
        await Promise.resolve()
        await Promise.resolve()
        await Promise.resolve()
      })
      expect(screen.getByText('Publish job queued')).toBeTruthy()

      await act(async () => {
        vi.advanceTimersByTime(3000)
        await Promise.resolve()
        await Promise.resolve()
      })
      expect(screen.getByText('Không tải được tiến trình dry-run.')).toBeTruthy()
      expect(calls.filter(call => call.url === '/api/publish-jobs/job-1/progress')).toHaveLength(2)

      await act(async () => {
        vi.advanceTimersByTime(3000)
        await Promise.resolve()
        await Promise.resolve()
      })
      expect(screen.getByText('Dry-run target complete')).toBeTruthy()
      expect(calls.filter(call => call.url === '/api/publish-jobs/job-1/progress')).toHaveLength(3)
    } finally {
      vi.useRealTimers()
    }
  })

  it('ignores stale progress responses from an older job', async () => {
    vi.useFakeTimers()
    const firstPollProgress = deferredResponse()
    let jobCreateCount = 0
    let jobOneProgressCount = 0
    vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
      calls.push({ url, init })
      if (url.startsWith('/api/channels/selector')) return jsonResponse(selectorResponse)
      if (url === '/api/media-assets') return jsonResponse([])
      if (url === '/api/content-items') return jsonResponse({ id: `content-${jobCreateCount + 1}`, title: 'ZooPost dry-run', body: 'Xin chào [r]', syntax_mode: 'zoopost', status: 'draft' })
      if (url === '/api/publish-jobs' && init?.method === 'POST') {
        jobCreateCount += 1
        return jsonResponse({ id: `job-${jobCreateCount}`, status: 'queued', dry_run: true, created_at: '2026-05-16T10:30:00Z', targets: [{ id: `target-${jobCreateCount}`, channel_id: 'channel-1', status: 'queued' }] })
      }
      if (url === '/api/publish-jobs?limit=5') return jsonResponse([])
      if (url === '/api/publish-jobs/job-1/progress') {
        jobOneProgressCount += 1
        return jobOneProgressCount === 1
          ? jsonResponse(progressPayload('job-1', 'queued', 0, 'First job queued'))
          : firstPollProgress.pending
      }
      if (url === '/api/publish-jobs/job-2/progress') return jsonResponse(progressPayload('job-2', 'queued', 0, 'Second job queued'))
      return Promise.resolve({ ok: false, status: 404, text: () => Promise.resolve(`missing mock ${url}`) } as Response)
    }))

    try {
      render(<AutoPostFanpagePage />)
      await act(async () => {
        await Promise.resolve()
        await Promise.resolve()
      })

      expect(screen.getByText('ZooPost Fanpage')).toBeTruthy()
      fireEvent.click(screen.getByLabelText(/ZooPost Fanpage/))
      await act(async () => {
        fireEvent.click(screen.getByText('BẮT ĐẦU ĐĂNG BÀI (DRY-RUN)'))
        await Promise.resolve()
        await Promise.resolve()
        await Promise.resolve()
      })
      expect(screen.getByText('First job queued')).toBeTruthy()

      await act(async () => {
        vi.advanceTimersByTime(3000)
        await Promise.resolve()
      })
      expect(calls.filter(call => call.url === '/api/publish-jobs/job-1/progress')).toHaveLength(2)

      fireEvent.click(screen.getByText('BẮT ĐẦU ĐĂNG BÀI (DRY-RUN)'))
      await act(async () => {
        await Promise.resolve()
        await Promise.resolve()
        await Promise.resolve()
      })
      expect(screen.getByText('Second job queued')).toBeTruthy()

      await act(async () => {
        firstPollProgress.resolve(progressPayload('job-1', 'posted', 100, 'First job stale complete'))
        await firstPollProgress.pending
      })

      expect(screen.queryByText('First job stale complete')).toBeNull()
      expect(screen.getByText('Second job queued')).toBeTruthy()
      expect(screen.getByText('0%')).toBeTruthy()
    } finally {
      vi.useRealTimers()
    }
  })

  it('does not publish stale content if the draft changes while saving', async () => {
    const contentSave = deferredResponse({ id: 'content-stale', title: 'ZooPost dry-run', body: 'Old body', syntax_mode: 'zoopost', status: 'draft' })
    vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
      calls.push({ url, init })
      if (url.startsWith('/api/channels/selector')) return jsonResponse(selectorResponse)
      if (url === '/api/content-items') return contentSave.pending
      if (url === '/api/publish-jobs' && init?.method === 'POST') return jsonResponse({ id: 'job-1', status: 'queued', dry_run: true, created_at: '2026-05-16T10:30:00Z', targets: [{ id: 'target-1', channel_id: 'channel-1', status: 'queued' }] })
      if (url === '/api/publish-jobs?limit=5') return jsonResponse([])
      return Promise.resolve({ ok: false, status: 404, text: () => Promise.resolve(`missing mock ${url}`) } as Response)
    }))

    render(<AutoPostFanpagePage />)

    expect(await screen.findByText('ZooPost Fanpage')).toBeTruthy()
    fireEvent.click(screen.getByLabelText(/ZooPost Fanpage/))
    const bodyEditor = screen.getByDisplayValue(/Nội dung A/)
    fireEvent.change(bodyEditor, { target: { value: 'Old body' } })
    fireEvent.click(screen.getByText('BẮT ĐẦU ĐĂNG BÀI (DRY-RUN)'))
    fireEvent.change(bodyEditor, { target: { value: 'New body' } })

    await act(async () => {
      contentSave.resolve()
      await contentSave.pending
    })

    await waitFor(() => expect(screen.getByText(/Nội dung đã thay đổi/)).toBeTruthy())
    expect(calls.some(call => call.url === '/api/publish-jobs' && call.init?.method === 'POST')).toBe(false)
  })
})
