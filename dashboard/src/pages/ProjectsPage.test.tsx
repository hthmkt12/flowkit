import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import ProjectsPage from './ProjectsPage'
import { fetchAPI, postAPI, patchAPI } from '../api/client'
import type { Project } from '../types/projects'

vi.mock('../api/client', () => ({
  fetchAPI: vi.fn(),
  postAPI: vi.fn(),
  patchAPI: vi.fn(),
}))

const mockFetchAPI = vi.mocked(fetchAPI)
const mockPostAPI = vi.mocked(postAPI)

const createdProject: Project = {
  id: 'project-created',
  tenant_id: 'tenant-a',
  name: 'Dry Run Only Project',
  niche: 'beauty',
  status: 'active',
  safety_policy_id: null,
  live_enabled: false,
  dry_run_required: true,
  default_autopilot_mode: 'guarded_autopilot',
  allowed_target_types: ['fanpage', 'group', 'post', 'lead'],
  kill_switch_enabled: false,
  metadata: {},
  created_at: '2026-07-04T00:00:00Z',
  updated_at: '2026-07-04T00:00:00Z',
}

describe('ProjectsPage', () => {
  beforeEach(() => {
    mockFetchAPI.mockImplementation(async path => {
      if (path === '/api/projects') return []
      if (path === '/api/channels') return []
      throw new Error(`Unexpected fetch path: ${path}`)
    })
    mockPostAPI.mockResolvedValue(createdProject)
    vi.mocked(patchAPI).mockResolvedValue(createdProject)
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('creates new projects with dry-run-only safety flags', async () => {
    render(<ProjectsPage />)

    fireEvent.change(await screen.findByLabelText('Project name'), {
      target: { value: createdProject.name },
    })
    fireEvent.change(screen.getByLabelText('Project niche'), {
      target: { value: createdProject.niche },
    })

    expect(screen.getByText(/Live Mutation locked in current phase/i)).toBeTruthy()
    expect(screen.getByText(/live_enabled=false and dry_run_required=true/i)).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: /create dry-run-only project/i }))

    await waitFor(() => {
      expect(mockPostAPI).toHaveBeenCalledWith(
        '/api/projects',
        expect.objectContaining({
          name: createdProject.name,
          niche: createdProject.niche,
          live_enabled: false,
          dry_run_required: true,
        })
      )
    })
  })
})
