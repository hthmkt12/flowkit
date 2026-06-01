import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import AccountsPage from './AccountsPage'
import type { Account } from '../types'

function account(overrides: Partial<Account> = {}): Account {
  return {
    id: 'account-1',
    name: 'Pilot Account',
    fb_uid: 'safe-fb-uid',
    email: 'pilot@example.com',
    status: 'ACTIVE',
    profile_url: null,
    avatar_url: null,
    notes: null,
    cookies_valid: 1,
    last_active: null,
    daily_posts: 0,
    daily_messages: 0,
    daily_likes: 0,
    daily_comments: 0,
    daily_friends: 0,
    daily_reset_at: null,
    created_at: '2026-05-25T00:00:00Z',
    updated_at: '2026-05-25T00:00:00Z',
    ...overrides,
  }
}

function jsonResponse(body: unknown) {
  return Promise.resolve({ ok: true, status: 200, text: () => Promise.resolve(JSON.stringify(body)) } as Response)
}

describe('AccountsPage', () => {
  const calls: Array<{ url: string; init?: RequestInit }> = []

  beforeEach(() => {
    calls.length = 0
    window.localStorage.setItem('zoopostBearerToken', 'browser-token')
    vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
      calls.push({ url, init })
      if (url === '/api/accounts') return jsonResponse([account()])
      if (url === '/api/accounts/extension-status') return jsonResponse({ accounts: [] })
      if (url === '/api/accounts/account-1') return jsonResponse(account({ status: 'PAUSED' }))
      return Promise.resolve({ ok: false, status: 404, text: () => Promise.resolve(`missing mock ${url}`) } as Response)
    }))
  })

  afterEach(() => {
    cleanup()
    window.localStorage.clear()
    vi.unstubAllGlobals()
  })

  it('uses the authenticated API client when patching account status', async () => {
    render(<AccountsPage />)

    expect(await screen.findByText('Pilot Account')).toBeTruthy()
    fireEvent.change(screen.getByDisplayValue('ACTIVE'), { target: { value: 'PAUSED' } })

    await waitFor(() => {
      const patch = calls.find(call => call.url === '/api/accounts/account-1' && call.init?.method === 'PATCH')
      expect(patch?.init?.headers).toMatchObject({ Authorization: 'Bearer browser-token' })
      expect(patch?.init?.body).toBe(JSON.stringify({ status: 'PAUSED' }))
    })
  })
})
