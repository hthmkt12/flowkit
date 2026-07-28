import type { WorkflowAnalysis, WorkflowEvent } from '../types/workflows'

type Props = { events?: WorkflowEvent[]; analysis?: WorkflowAnalysis; loading?: boolean; error?: string }

export default function WorkflowLabPage({ events = [], analysis, loading = false, error }: Props) {
  if (loading) return <div role="status">Loading Workflow Lab…</div>
  if (error) return <div role="alert">Unable to load Workflow Lab: {error}</div>
  return (
    <section aria-labelledby="workflow-lab-title">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 id="workflow-lab-title" className="text-xl font-bold">Workflow Lab</h1>
          <p className="text-sm" style={{ color: 'var(--muted)' }}>Local metadata inspection · read-only · no replay</p>
        </div>
        <span aria-label="read-only status" className="rounded px-2 py-1 text-xs font-semibold" style={{ background: '#dcfce7', color: '#166534' }}>READ_ONLY</span>
      </div>
      {analysis && <div className="rounded border p-3 mb-4" style={{ borderColor: 'var(--border)', background: 'var(--surface)' }}>
        <div className="text-sm font-semibold">Replayability: {analysis.replayability}</div>
        <div className="text-xs" style={{ color: 'var(--muted)' }}>{analysis.eventCount} sanitized events · execution disabled</div>
      </div>}
      {!events.length ? <p className="text-sm" style={{ color: 'var(--muted)' }}>No captures available.</p> : <div className="overflow-auto rounded border" style={{ borderColor: 'var(--border)' }}>
        <table className="w-full text-left text-xs"><thead><tr><th className="p-2">Method</th><th className="p-2">Host</th><th className="p-2">Path shape</th><th className="p-2">Status</th></tr></thead><tbody>
          {events.slice(0, 100).map((event, index) => <tr key={`${event.captureId}-${index}`}><td className="p-2">{event.method}</td><td className="p-2">{event.host}</td><td className="p-2 break-all">{event.path}</td><td className="p-2">{event.status ?? '—'}</td></tr>)}
        </tbody></table>
      </div>}
    </section>
  )
}
