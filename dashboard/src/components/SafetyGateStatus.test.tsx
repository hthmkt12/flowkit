import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import type { AgentStatus } from '../types'
import SafetyGateStatus from './SafetyGateStatus'

function status(overrides: Partial<AgentStatus['safety_gate']> = {}): AgentStatus {
  return {
    extension: {
      connected: true,
      session_count: 1,
      sessions: [{
        fb_uid: 'safe-profile',
        logged_in: true,
        uptime_s: 12,
        stale: false,
      }],
      total_connects: 1,
      total_disconnects: 0,
    },
    safety_gate: {
      live_actions_enabled: false,
      dry_run_default: true,
      approval_required: true,
      live_auth_ready: false,
      active_live_arms: [],
      ...overrides,
    },
  }
}

describe('SafetyGateStatus', () => {
  afterEach(() => {
    cleanup()
  })

  it('shows live auth readiness and active live arm count', () => {
    render(<SafetyGateStatus status={status({ live_auth_ready: true, active_live_arms: [{ id: 'arm-1' }, { id: 'arm-2' }] })} />)

    expect(screen.getByText(/live auth ready: ready/i)).toBeTruthy()
    expect(screen.getByText(/active live arms: 2 active/i)).toBeTruthy()
  })

  it('shows when live auth is not ready and no live arms are active', () => {
    render(<SafetyGateStatus status={status()} />)

    expect(screen.getByText(/live auth ready: not ready/i)).toBeTruthy()
    expect(screen.getByText(/active live arms: none/i)).toBeTruthy()
  })
})
