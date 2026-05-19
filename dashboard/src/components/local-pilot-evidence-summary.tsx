import { Clipboard, FileCheck2 } from 'lucide-react'
import type { CSSProperties } from 'react'

type Props = {
  readySessions: number
  completedDryRuns: number
  failedTargets: number
  auditRecords: number
  selectableChannels: number
}

export function LocalPilotEvidenceSummary({ readySessions, completedDryRuns, failedTargets, auditRecords, selectableChannels }: Props) {
  const summary = [
    'ZooPost local pilot evidence:',
    `- Ready dry-run agent sessions: ${readySessions}`,
    `- Completed dry-run jobs: ${completedDryRuns}`,
    `- Failed targets: ${failedTargets}`,
    `- Audit records visible: ${auditRecords}`,
    `- Selectable fanpage channels: ${selectableChannels}`,
    '- Safety: dry-run only; no credentials, cookies, profile URLs, or raw Facebook IDs shown in dashboard evidence.',
  ].join('\n')

  async function copySummary() {
    await navigator.clipboard?.writeText(summary)
  }

  return (
    <section style={panelStyle()}>
      <div style={titleBarStyle}>
        <div style={titleStyle}>
          <FileCheck2 size={16} />
          Pilot Summary
        </div>
        <button type="button" onClick={copySummary} style={copyButtonStyle}>
          <Clipboard size={14} />
          Copy
        </button>
      </div>
      <div style={summaryStyle}>{summary}</div>
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

const summaryStyle: CSSProperties = {
  whiteSpace: 'pre-line',
  lineHeight: 1.5,
  fontSize: '12px',
  color: 'var(--text)',
  border: '1px solid var(--border)',
  borderRadius: '10px',
  background: 'var(--surface)',
  padding: '12px',
}
