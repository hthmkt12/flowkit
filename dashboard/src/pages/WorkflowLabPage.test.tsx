import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import WorkflowLabPage from './WorkflowLabPage'

describe('WorkflowLabPage', () => {
  it('shows safe read-only empty state', () => {
    render(<WorkflowLabPage />)
    expect(screen.getByText('No captures available.')).toBeTruthy()
    expect(screen.getByLabelText('read-only status')).toBeTruthy()
    expect(screen.queryByRole('button')).toBeNull()
  })
  it('renders bounded sanitized metadata without links', () => {
    render(<WorkflowLabPage analysis={{ captureId: 'cap', schemaVersion: 1, replayability: 'DOM_FALLBACK', readOnly: true, executeAllowed: false, eventCount: 1 }} events={[{ captureId: 'cap', method: 'GET', host: 'www.facebook.com', path: '/api/:segment', status: 200, resourceType: 'XHR', timingMs: 2, queryShape: [] }]} />)
    expect(screen.getByText(/DOM_FALLBACK/)).toBeTruthy()
    expect(screen.queryAllByRole('link')).toHaveLength(0)
    expect(screen.getByText('/api/:segment')).toBeTruthy()
  })
})
