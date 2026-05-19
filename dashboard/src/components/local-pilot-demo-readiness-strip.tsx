import { CheckCircle2, CircleAlert, EyeOff, Radio, ShieldCheck } from 'lucide-react'
import type { CSSProperties, ReactNode } from 'react'

type Props = {
  readySessions: number
  completedDryRuns: number
}

export function LocalPilotDemoReadinessStrip({ readySessions, completedDryRuns }: Props) {
  const readyToDemo = readySessions > 0 && completedDryRuns > 0
  return (
    <section style={panelStyle(readyToDemo)}>
      <div style={headerStyle}>
        <div>
          <div style={titleStyle}>Demo readiness</div>
          <div style={subtitleStyle}>Sales pilot proof: local extension online, dry-run posted, live actions stay off.</div>
        </div>
        <span style={statusStyle(readyToDemo)}>
          {readyToDemo ? <CheckCircle2 size={15} /> : <CircleAlert size={15} />}
          {readyToDemo ? 'Ready to demo' : 'Needs attention'}
        </span>
      </div>
      <div style={gridStyle}>
        <ReadinessItem ok={completedDryRuns > 0} icon={<CheckCircle2 size={16} />} title="Dry-run posted" detail={`${completedDryRuns} completed job(s)`} />
        <ReadinessItem ok icon={<ShieldCheck size={16} />} title="Live actions off" detail="Cloud jobs stay dry-run only" />
        <ReadinessItem ok={readySessions > 0} icon={<Radio size={16} />} title="Extension ready" detail={`${readySessions} ready session(s)`} />
        <ReadinessItem ok icon={<EyeOff size={16} />} title="Customer-safe evidence" detail="No raw Facebook IDs or credentials" />
      </div>
    </section>
  )
}

function ReadinessItem({ ok, icon, title, detail }: { ok: boolean; icon: ReactNode; title: string; detail: string }) {
  return (
    <div style={itemStyle(ok)}>
      <div style={{ color: ok ? '#16a34a' : '#d97706' }}>{icon}</div>
      <div>
        <div style={itemTitleStyle}>{title}</div>
        <div style={detailStyle}>{detail}</div>
      </div>
    </div>
  )
}

function panelStyle(ok: boolean): CSSProperties {
  const color = ok ? '#16a34a' : '#d97706'
  return {
    background: `${color}10`,
    border: `1px solid ${color}44`,
    borderRadius: '14px',
    padding: '16px',
  }
}

const headerStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: '12px',
  flexWrap: 'wrap',
  marginBottom: '12px',
}

const titleStyle: CSSProperties = {
  fontSize: '16px',
  fontWeight: 850,
}

const subtitleStyle: CSSProperties = {
  color: 'var(--muted)',
  fontSize: '12px',
  marginTop: '3px',
}

function statusStyle(ok: boolean): CSSProperties {
  const color = ok ? '#16a34a' : '#d97706'
  return {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '7px',
    border: `1px solid ${color}55`,
    background: `${color}16`,
    color,
    borderRadius: '999px',
    padding: '7px 10px',
    fontSize: '12px',
    fontWeight: 850,
    whiteSpace: 'nowrap',
  }
}

const gridStyle: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
  gap: '10px',
}

function itemStyle(ok: boolean): CSSProperties {
  return {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    border: `1px solid ${ok ? '#16a34a33' : '#d9770633'}`,
    background: 'var(--card)',
    borderRadius: '10px',
    padding: '10px 12px',
    minHeight: '62px',
  }
}

const itemTitleStyle: CSSProperties = {
  fontWeight: 850,
  fontSize: '12px',
}

const detailStyle: CSSProperties = {
  color: 'var(--muted)',
  fontSize: '11px',
  marginTop: '2px',
}
