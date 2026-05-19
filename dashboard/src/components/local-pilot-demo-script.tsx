import { Clipboard, Presentation } from 'lucide-react'
import type { CSSProperties } from 'react'

const demoScript = [
  'This pilot is local and dry-run only; no live Facebook action is approved or executed.',
  'The agent is paired to ZooPost Cloud and reports a dry-run-ready browser session.',
  'A fanpage dry-run job is dispatched through the same Cloud-to-local path planned for the pilot.',
  'Evidence here shows readiness, completion, audit trail, and sanitized channel state without exposing credentials or raw Facebook IDs.',
].join('\n')

const proofPoints = [
  'Ready agent session exists',
  'Dry-run job completed',
  'Audit evidence recorded',
  'Safety boundary visible',
]

export function LocalPilotDemoScript() {
  async function copyScript() {
    await navigator.clipboard?.writeText(demoScript)
  }

  return (
    <section style={panelStyle()}>
      <div style={titleBarStyle}>
        <div style={titleStyle}>
          <Presentation size={16} />
          Sales Demo Script
        </div>
        <button type="button" onClick={copyScript} style={copyButtonStyle}>
          <Clipboard size={14} />
          Copy
        </button>
      </div>
      <div style={layoutStyle}>
        <div style={scriptStyle}>{demoScript}</div>
        <div style={{ display: 'grid', gap: '8px' }}>
          {proofPoints.map(point => (
            <div key={point} style={proofStyle}>{point}</div>
          ))}
        </div>
      </div>
    </section>
  )
}

function panelStyle(): CSSProperties {
  return { background: 'var(--card)', border: '1px solid var(--border)', borderRadius: '14px', padding: '16px' }
}

const titleBarStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: '12px',
  marginBottom: '12px',
}

const titleStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
  fontWeight: 850,
}

const layoutStyle: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
  gap: '12px',
  alignItems: 'start',
}

const scriptStyle: CSSProperties = {
  whiteSpace: 'pre-line',
  lineHeight: 1.5,
  fontSize: '12px',
  color: 'var(--text)',
  border: '1px solid var(--border)',
  borderRadius: '10px',
  background: 'var(--surface)',
  padding: '12px',
}

const proofStyle: CSSProperties = {
  border: '1px solid #16a34a55',
  background: '#16a34a12',
  color: '#16a34a',
  borderRadius: '999px',
  padding: '7px 10px',
  fontSize: '11px',
  fontWeight: 850,
  textAlign: 'center',
}

const copyButtonStyle: CSSProperties = {
  border: 0,
  borderRadius: '10px',
  background: '#2563eb',
  color: '#fff',
  padding: '8px 10px',
  display: 'inline-flex',
  alignItems: 'center',
  gap: '7px',
  fontSize: '12px',
  fontWeight: 800,
  cursor: 'pointer',
}
