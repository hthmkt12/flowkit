import { ShieldCheck, ShieldAlert, Wifi, WifiOff } from 'lucide-react'
import type { AgentStatus } from '../types'

interface SafetyGateStatusProps {
  status: AgentStatus | null
}

function StatusPill({ label, active, safeWhenActive = true }: { label: string; active: boolean; safeWhenActive?: boolean }) {
  const safe = active === safeWhenActive
  return (
    <span style={{
      padding: '4px 8px',
      borderRadius: '999px',
      background: safe ? 'rgba(34, 197, 94, 0.12)' : 'rgba(239, 68, 68, 0.12)',
      border: `1px solid ${safe ? 'rgba(34, 197, 94, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
      color: safe ? 'var(--green)' : 'var(--red)',
      fontSize: '10px',
      fontWeight: 700,
      textTransform: 'uppercase',
      letterSpacing: '0.04em',
    }}>
      {label}: {active ? 'on' : 'off'}
    </span>
  )
}

export default function SafetyGateStatus({ status }: SafetyGateStatusProps) {
  const safety = status?.safety_gate
  const safetyKnown = Boolean(safety)
  const extension = status?.extension
  const liveEnabled = safety?.live_actions_enabled ?? false
  const dryRunDefault = safety?.dry_run_default ?? true
  const approvalRequired = safety?.approval_required ?? true
  const connected = extension?.connected ?? false
  const loggedInSessions = extension?.sessions?.filter(session => session.logged_in && session.fb_uid).length ?? 0
  const protectedMode = !liveEnabled && dryRunDefault && approvalRequired

  if (!safetyKnown) {
    return (
      <div style={{
        background: 'linear-gradient(135deg, rgba(245,158,11,0.14), rgba(59,130,246,0.06))',
        border: '1px solid rgba(245,158,11,0.4)',
        borderRadius: '12px',
        padding: '16px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '12px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <ShieldAlert size={20} color="var(--yellow)" />
          <div>
            <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text)' }}>Safety Gate unavailable</div>
            <div style={{ fontSize: '11px', color: 'var(--muted)', marginTop: '2px' }}>
              Unable to verify dry-run, live-action, or approval flags.
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: connected ? 'var(--green)' : 'var(--red)', fontSize: '11px', fontWeight: 700 }}>
          {connected ? <Wifi size={14} /> : <WifiOff size={14} />}
          {connected ? `${loggedInSessions} session${loggedInSessions === 1 ? '' : 's'}` : 'extension unknown'}
        </div>
      </div>
    )
  }

  return (
    <div style={{
      background: protectedMode ? 'linear-gradient(135deg, rgba(34,197,94,0.12), rgba(59,130,246,0.08))' : 'linear-gradient(135deg, rgba(239,68,68,0.14), rgba(245,158,11,0.08))',
      border: `1px solid ${protectedMode ? 'rgba(34,197,94,0.35)' : 'rgba(239,68,68,0.4)'}`,
      borderRadius: '12px',
      padding: '16px',
      display: 'flex',
      flexDirection: 'column',
      gap: '12px',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {protectedMode ? <ShieldCheck size={20} color="var(--green)" /> : <ShieldAlert size={20} color="var(--red)" />}
          <div>
            <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text)' }}>Safety Gate</div>
            <div style={{ fontSize: '11px', color: 'var(--muted)', marginTop: '2px' }}>
              {protectedMode ? 'Protected dry-run mode active' : 'Review live-action safety flags before dispatch'}
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: connected ? 'var(--green)' : 'var(--red)', fontSize: '11px', fontWeight: 700 }}>
          {connected ? <Wifi size={14} /> : <WifiOff size={14} />}
          {connected ? `${loggedInSessions} session${loggedInSessions === 1 ? '' : 's'}` : 'extension offline'}
        </div>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
        <StatusPill label="live actions" active={liveEnabled} safeWhenActive={false} />
        <StatusPill label="dry-run default" active={dryRunDefault} />
        <StatusPill label="approval required" active={approvalRequired} />
      </div>
    </div>
  )
}
