import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { PilotReadinessStrip } from './pilot-readiness-strip'

describe('PilotReadinessStrip', () => {
  afterEach(() => {
    cleanup()
  })

  it('shows all-pass state when every check passes', () => {
    render(
      <PilotReadinessStrip
        cloudReachable={true}
        fbkitReachable={true}
        dashboardReachable={true}
        fbSessionLoggedIn={true}
        agentHasPublishDryRun={true}
        liveDisabled={true}
        evidenceFresh={true}
        selectableChannels={2}
      />,
    )

    expect(screen.getByText('All checks pass')).toBeTruthy()
    expect(screen.getByText('Cloud reachable')).toBeTruthy()
    expect(screen.getByText('ZooPost Cloud online')).toBeTruthy()
    expect(screen.getByText('FB session logged-in')).toBeTruthy()
    expect(screen.getByText('fb_uid detected')).toBeTruthy()
    expect(screen.getByText('Agent publish-dry-run')).toBeTruthy()
    expect(screen.getByText('capability reported')).toBeTruthy()
    expect(screen.getByText('Live disabled')).toBeTruthy()
    expect(screen.getByText('dry-run phase enforced')).toBeTruthy()
    expect(screen.getByText('2 selectable channel(s)')).toBeTruthy()
  })

  it('shows action required when a critical check fails', () => {
    render(
      <PilotReadinessStrip
        cloudReachable={true}
        fbkitReachable={false}
        dashboardReachable={true}
        fbSessionLoggedIn={false}
        agentHasPublishDryRun={true}
        liveDisabled={true}
        evidenceFresh={true}
        selectableChannels={0}
      />,
    )

    expect(screen.getByText('Action required')).toBeTruthy()
    expect(screen.getByText('FBKit offline')).toBeTruthy()
    expect(screen.getByText('no logged-in profile')).toBeTruthy()
  })

  it('shows STOP warning when live is not disabled', () => {
    render(
      <PilotReadinessStrip
        cloudReachable={true}
        fbkitReachable={true}
        dashboardReachable={true}
        fbSessionLoggedIn={true}
        agentHasPublishDryRun={true}
        liveDisabled={false}
        evidenceFresh={true}
        selectableChannels={1}
      />,
    )

    expect(screen.getByText('Action required')).toBeTruthy()
    expect(screen.getByText('LIVE IS ENABLED - STOP')).toBeTruthy()
  })

  it('shows needs attention when only warn-level checks fail', () => {
    render(
      <PilotReadinessStrip
        cloudReachable={true}
        fbkitReachable={true}
        dashboardReachable={true}
        fbSessionLoggedIn={true}
        agentHasPublishDryRun={true}
        liveDisabled={true}
        evidenceFresh={false}
        selectableChannels={0}
      />,
    )

    expect(screen.getByText('Needs attention')).toBeTruthy()
    expect(screen.getByText('evidence stale or missing')).toBeTruthy()
    expect(screen.getByText('0 selectable channel(s)')).toBeTruthy()
  })

  it('does not pass when safety status is unavailable', () => {
    render(
      <PilotReadinessStrip
        cloudReachable={true}
        fbkitReachable={true}
        dashboardReachable={true}
        fbSessionLoggedIn={true}
        agentHasPublishDryRun={true}
        liveDisabled={null}
        evidenceFresh={null}
        selectableChannels={1}
      />,
    )

    expect(screen.getByText('Needs attention')).toBeTruthy()
    expect(screen.getByText('safety status unavailable - do not proceed')).toBeTruthy()
    expect(screen.getByText('evidence freshness unavailable')).toBeTruthy()
  })
})
