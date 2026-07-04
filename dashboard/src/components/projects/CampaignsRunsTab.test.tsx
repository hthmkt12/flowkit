import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import CampaignsRunsTab from './CampaignsRunsTab'
import { fetchAPI, postAPI } from '../../api/client'
import type { AffiliateCampaign, Project } from '../../types/projects'

vi.mock('../../api/client', () => ({
  fetchAPI: vi.fn(),
  postAPI: vi.fn(),
}))

const mockFetchAPI = vi.mocked(fetchAPI)
const mockPostAPI = vi.mocked(postAPI)

const project: Project = {
  id: 'project-1',
  tenant_id: 'tenant-a',
  name: 'Live Locked Project',
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

const campaign: AffiliateCampaign = {
  id: 'campaign-1',
  tenant_id: 'tenant-a',
  project_id: project.id,
  created_by: 'user-a',
  name: 'Fanpage Pilot',
  offer_name: null,
  affiliate_network: null,
  status: 'ready',
  default_caption: {},
  link_template: {},
  metadata: {},
  created_at: '2026-07-04T00:00:00Z',
  updated_at: '2026-07-04T00:00:00Z',
}

describe('CampaignsRunsTab', () => {
  beforeEach(() => {
    mockFetchAPI.mockImplementation(async path => {
      if (path === `/api/projects/${project.id}/campaigns`) return [campaign]
      if (path === `/api/projects/${project.id}/runs`) return []
      throw new Error(`Unexpected fetch path: ${path}`)
    })
    mockPostAPI.mockResolvedValue({ job_count: 1 })
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('keeps live campaign runs locked even when the project live flag is enabled', async () => {
    const onMessage = vi.fn()

    render(<CampaignsRunsTab project={project} actionPending={false} onMessage={onMessage} />)

    const liveButton = await screen.findByRole('button', { name: /live run locked/i })
    expect((liveButton as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByText(/campaign live dispatch is still locked/i)).toBeTruthy()

    fireEvent.click(liveButton)

    expect(mockPostAPI).not.toHaveBeenCalledWith(
      expect.stringContaining('/runs/live'),
      expect.anything()
    )
  })

  it('still launches dry-runs through the dry-run endpoint', async () => {
    const onMessage = vi.fn()

    render(<CampaignsRunsTab project={project} actionPending={false} onMessage={onMessage} />)

    fireEvent.click(await screen.findByRole('button', { name: /dry-run/i }))

    await waitFor(() => {
      expect(mockPostAPI).toHaveBeenCalledWith(
        `/api/projects/${project.id}/campaigns/${campaign.id}/runs/dry-run`,
        expect.objectContaining({ spacing_minutes: 30 })
      )
    })
  })
})
