import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import OverviewPolicyTab from './OverviewPolicyTab'
import ProjectList from './ProjectList'
import type { Project } from '../../types/projects'

const liveFlagProject: Project = {
  id: 'project-live-flag',
  tenant_id: 'tenant-a',
  name: 'Live Flag Project',
  niche: 'beauty',
  status: 'active',
  safety_policy_id: null,
  live_enabled: true,
  dry_run_required: true,
  default_autopilot_mode: 'guarded_autopilot',
  allowed_target_types: ['fanpage'],
  kill_switch_enabled: false,
  metadata: {},
  created_at: '2026-07-04T00:00:00Z',
  updated_at: '2026-07-04T00:00:00Z',
}

describe('project live flag safety copy', () => {
  afterEach(cleanup)

  it('labels enabled project live flags as locked rather than allowed', () => {
    render(
      <OverviewPolicyTab
        project={liveFlagProject}
        actionPending={false}
        onToggleKillSwitch={vi.fn()}
        onTogglePause={vi.fn()}
        onArchive={vi.fn()}
      />
    )

    expect(screen.getByText('ON - LOCKED')).toBeTruthy()
    expect(screen.getByText(/live execution remains locked/i)).toBeTruthy()
    expect(screen.queryByText('CHO PHÉP')).toBeNull()
  })

  it('shows project list live state as a locked flag', () => {
    render(
      <ProjectList
        projects={[liveFlagProject]}
        loading={false}
        selectedProjectId={liveFlagProject.id}
        onToggleKillSwitch={vi.fn()}
        onTogglePause={vi.fn()}
        onArchive={vi.fn()}
        onSelectProject={vi.fn()}
      />
    )

    expect(screen.getByText('Live flag: ON - LOCKED')).toBeTruthy()
    expect(screen.queryByText('Live: ON')).toBeNull()
  })
})
