import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import ApprovalQueueTab from './ApprovalQueueTab'
import { fetchAPI, postAPI } from '../../api/client'
import type { Project } from '../../types/projects'

vi.mock('../../api/client', () => ({
  fetchAPI: vi.fn(),
  postAPI: vi.fn(),
}))

const mockFetchAPI = vi.mocked(fetchAPI)
const mockPostAPI = vi.mocked(postAPI)

const project: Project = {
  id: 'project-approval-lock',
  tenant_id: 'tenant-a',
  name: 'Approval Lock Project',
  niche: null,
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

describe('ApprovalQueueTab', () => {
  beforeEach(() => {
    mockFetchAPI.mockResolvedValue([
      {
        id: 'task-live-1',
        account_id: 'account-1',
        task_type: 'facebook.post_text',
        status: 'PENDING',
        payload: { projectId: project.id, content: 'future live approval' },
        ref_id: null,
        priority: 5,
        scheduled_at: null,
        created_at: '2026-07-04T00:00:00Z',
        updated_at: '2026-07-04T00:00:00Z',
      },
    ])
    mockPostAPI.mockResolvedValue({})
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('shows live approvals as locked audit-only items', async () => {
    render(<ApprovalQueueTab project={project} onMessage={vi.fn()} />)

    const liveButton = await screen.findByRole('button', { name: /live locked/i })

    expect((liveButton as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByText(/approval cannot arm live dispatch/i)).toBeTruthy()
    expect(mockPostAPI).not.toHaveBeenCalledWith('/api/tasks/task-live-1/approve')
  })
})
