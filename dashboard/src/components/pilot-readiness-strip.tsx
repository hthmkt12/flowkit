import { CheckCircle2, CircleAlert, Radio } from 'lucide-react'
import type { CSSProperties, ReactNode } from 'react'

type Props = {
  cloudReachable: boolean
  fbkitReachable: boolean
  dashboardReachable: boolean
  fbSessionLoggedIn: boolean
  agentHasPublishDryRun: boolean
  liveDisabled: boolean | null
  evidenceFresh: boolean | null
  selectableChannels: number
}

type CheckStatus = 'pass' | 'fail' | 'warn' | 'skip'

function checkStatus(ok: boolean | null): CheckStatus {
  if (ok === null) return 'skip'
  return ok ? 'pass' : 'fail'
}

export function PilotReadinessStrip(props: Props) {
  const checks: Array<{ label: string; status: CheckStatus; detail: string }> = [
    { label: 'Cloud reachable', status: checkStatus(props.cloudReachable), detail: props.cloudReachable ? 'ZooPost Cloud online' : 'Cloud offline' },
    { label: 'FBKit reachable', status: checkStatus(props.fbkitReachable), detail: props.fbkitReachable ? 'FBKit agent online' : 'FBKit offline' },
    { label: 'Dashboard reachable', status: checkStatus(props.dashboardReachable), detail: props.dashboardReachable ? 'Dashboard serving' : 'Dashboard offline' },
    { label: 'FB session logged-in', status: checkStatus(props.fbSessionLoggedIn), detail: props.fbSessionLoggedIn ? 'fb_uid detected' : 'no logged-in profile' },
    { label: 'Agent publish-dry-run', status: checkStatus(props.agentHasPublishDryRun), detail: props.agentHasPublishDryRun ? 'capability reported' : 'capability missing' },
    { label: 'Live disabled', status: props.liveDisabled === null ? 'warn' : props.liveDisabled ? 'pass' : 'fail', detail: props.liveDisabled === null ? 'safety status unavailable - do not proceed' : props.liveDisabled ? 'dry-run phase enforced' : 'LIVE IS ENABLED - STOP' },
    { label: 'Evidence fresh', status: props.evidenceFresh === null ? 'warn' : props.evidenceFresh ? 'pass' : 'warn', detail: props.evidenceFresh === null ? 'evidence freshness unavailable' : props.evidenceFresh ? 'evidence report current' : 'evidence stale or missing' },
    { label: 'Channel readiness', status: props.selectableChannels > 0 ? 'pass' : 'warn', detail: `${props.selectableChannels} selectable channel(s)` },
  ]

  const allPass = checks.every(c => c.status === 'pass')
  const hasFail = checks.some(c => c.status === 'fail')

  return (
    <section style={panelStyle(allPass, hasFail)}>
      <div style={headerStyle}>
        <div>
          <div style={titleStyle}>Pilot Readiness</div>
          <div style={subtitleStyle}>Cloud, FBKit, Dashboard, FB session, agent capability, live block, evidence, channels.</div>
        </div>
        <span style={statusBadgeStyle(allPass, hasFail)}>
          {allPass ? <CheckCircle2 size={15} /> : <CircleAlert size={15} />}
          {allPass ? 'All checks pass' : hasFail ? 'Action required' : 'Needs attention'}
        </span>
      </div>
      <div style={gridStyle}>
        {checks.map(check => (
          <ReadinessItem key={check.label} status={check.status} label={check.label} detail={check.detail} />
        ))}
      </div>
    </section>
  )
}

function ReadinessItem({ status, label, detail }: { status: CheckStatus; label: string; detail: string }) {
  const color = statusColor(status)
  const icon = statusIcon(status)
  return (
    <div style={itemStyle(status)}>
      <div style={{ color }}>{icon}</div>
      <div>
        <div style={itemTitleStyle}>{label}</div>
        <div style={detailStyle}>{detail}</div>
      </div>
    </div>
  )
}

function statusColor(status: CheckStatus): string {
  switch (status) {
    case 'pass': return '#16a34a'
    case 'fail': return '#dc2626'
    case 'warn': return '#d97706'
    case 'skip': return 'var(--muted)'
  }
}

function statusIcon(status: CheckStatus): ReactNode {
  switch (status) {
    case 'pass': return <CheckCircle2 size={16} />
    case 'fail': return <CircleAlert size={16} />
    case 'warn': return <CircleAlert size={16} />
    case 'skip': return <Radio size={16} />
  }
}

function panelStyle(allPass: boolean, hasFail: boolean): CSSProperties {
  const color = allPass ? '#16a34a' : hasFail ? '#dc2626' : '#d97706'
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

function statusBadgeStyle(allPass: boolean, hasFail: boolean): CSSProperties {
  const color = allPass ? '#16a34a' : hasFail ? '#dc2626' : '#d97706'
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
  gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
  gap: '10px',
}

function itemStyle(status: CheckStatus): CSSProperties {
  const color = statusColor(status)
  return {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    border: `1px solid ${color}33`,
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
