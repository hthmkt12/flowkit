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
  ],
  limit: 100,
}

function jsonResponse(body: unknown) {
  return Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response)
}

function deferredResponse(body: unknown) {
  let resolve!: () => void
  const pending = new Promise<Response>(promiseResolve => {
    resolve = () => promiseResolve({ ok: true, json: () => Promise.resolve(body) } as Response)
  })
  return { pending, resolve }
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
      if (url === '/api/publish-jobs') return jsonResponse({ id: 'job-1', status: 'queued', dry_run: true, targets: [{ id: 'target-1', channel_id: 'channel-1', status: 'queued' }] })
      if (url === '/api/publish-jobs/job-1/progress') return jsonResponse({
        job_id: 'job-1',
        status: 'queued',
        counts: { total: 1, queued: 1, dispatching: 0, posted: 0, failed: 0, cancelled: 0 },
        percent_complete: 0,
        targets: [{ id: 'target-1', channel_id: 'channel-1', status: 'queued', attempts: 0, external_post_id: null, external_post_url: null, error_code: null, error_message: null }],
        events: [{ id: 'event-1', type: 'job.queued', severity: 'info', message: 'Publish job queued', target_id: null, data: {} }],
      })
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

    const publishCall = calls.find(call => call.url === '/api/publish-jobs')
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

  it('does not publish stale content if the draft changes while saving', async () => {
    const contentSave = deferredResponse({ id: 'content-stale', title: 'ZooPost dry-run', body: 'Old body', syntax_mode: 'zoopost', status: 'draft' })
    vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
      calls.push({ url, init })
      if (url.startsWith('/api/channels/selector')) return jsonResponse(selectorResponse)
      if (url === '/api/content-items') return contentSave.pending
      if (url === '/api/publish-jobs') return jsonResponse({ id: 'job-1', status: 'queued', dry_run: true, targets: [{ id: 'target-1', channel_id: 'channel-1', status: 'queued' }] })
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
    expect(calls.some(call => call.url === '/api/publish-jobs')).toBe(false)
  })
})
