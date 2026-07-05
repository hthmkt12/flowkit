import { CheckCircle2, Clipboard, TerminalSquare } from 'lucide-react'
import type { CSSProperties } from 'react'

const pilotCommands = [
  {
    label: 'Gate A+B verification',
    command: '$python=(Resolve-Path \'.\\flowkit\\.venv\\Scripts\\python.exe\').Path; .\\scripts\\zoopost-verify-all.ps1 -Python $python -IncludeSafetyGate',
  },
  {
    label: 'Fresh paired stack setup',
    command: '.\\scripts\\demo-sales-local-pilot-ready.ps1 -StartPairedFbkit -StopExistingFbkit',
  },
  {
    label: 'Strict preflight only',
    command: '.\\scripts\\demo-sales-local-pilot-check.ps1 -RequireFacebookProfile',
  },
  {
    label: 'Save evidence report',
    command: '.\\scripts\\demo-sales-local-pilot-evidence.ps1',
  },
]

const pilotSteps = [
  'Load Chrome extension and sign in with the Facebook test profile.',
  'Run Gate A+B verification from the repository root with live actions disabled.',
  'Open Fanpage Dry Run and create one dry-run publish job.',
  'Return here to show readiness, job completion, audit evidence, and safety boundary.',
]

export function LocalPilotChecklist() {
  async function copyCommand(command: string) {
    await navigator.clipboard?.writeText(command)
  }

  return (
    <section style={panelStyle()}>
      <div style={titleStyle()}>
        <CheckCircle2 size={16} />
        Local Pilot Checklist
      </div>
      <div style={safetyNoteStyle}>
        Dry-run pilot only. Gate A+B must pass with live actions disabled before using this screen as handoff evidence.
      </div>
      <div style={layoutStyle}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {pilotSteps.map((step, index) => (
            <div key={step} style={rowStyle()}>
              <span style={stepNumberStyle}>{index + 1}</span>
              <span>{step}</span>
            </div>
          ))}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {pilotCommands.map(item => (
            <button key={item.label} type="button" onClick={() => copyCommand(item.command)} style={commandStyle}>
              <TerminalSquare size={15} />
              <span style={{ flex: 1 }}>
                <strong>{item.label}</strong>
                <code style={codeStyle}>{item.command}</code>
              </span>
              <Clipboard size={15} />
            </button>
          ))}
        </div>
      </div>
    </section>
  )
}

function panelStyle(): CSSProperties {
  return { background: 'var(--card)', border: '1px solid var(--border)', borderRadius: '14px', padding: '16px' }
}

function titleStyle(): CSSProperties {
  return { display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 850, marginBottom: '12px' }
}

const layoutStyle: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
  gap: '12px',
  alignItems: 'start',
}

function rowStyle(): CSSProperties {
  return {
    display: 'flex',
    alignItems: 'flex-start',
    gap: '10px',
    padding: '10px 12px',
    border: '1px solid var(--border)',
    borderRadius: '10px',
    background: 'var(--surface)',
    fontSize: '12px',
    lineHeight: 1.45,
  }
}

const stepNumberStyle: CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  minWidth: '22px',
  height: '22px',
  borderRadius: '999px',
  background: '#2563eb18',
  color: '#2563eb',
  fontWeight: 850,
}

const commandStyle: CSSProperties = {
  width: '100%',
  border: '1px solid var(--border)',
  borderRadius: '10px',
  background: 'var(--surface)',
  color: 'inherit',
  padding: '10px 12px',
  display: 'flex',
  alignItems: 'center',
  gap: '10px',
  textAlign: 'left',
  cursor: 'pointer',
}

const codeStyle: CSSProperties = {
  display: 'block',
  marginTop: '4px',
  color: 'var(--muted)',
  fontSize: '11px',
  overflowWrap: 'anywhere',
}

const safetyNoteStyle: CSSProperties = {
  marginBottom: '12px',
  color: '#d97706',
  fontSize: '12px',
  lineHeight: 1.45,
}
