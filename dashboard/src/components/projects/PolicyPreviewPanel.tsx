import type { CSSProperties } from 'react'
import { AlertCircle, ShieldAlert, ShieldCheck } from 'lucide-react'
import type { PolicyPreviewResult } from '../../types/projects'

interface PolicyPreviewPanelProps {
  preview: PolicyPreviewResult | null
  loading: boolean
}

function decisionBadge(decision: 'allow_auto' | 'require_approval' | 'block') {
  if (decision === 'allow_auto') {
    return { text: 'AUTO-ALLOW', color: 'var(--green)', icon: <ShieldCheck size={11} /> }
  }
  if (decision === 'require_approval') {
    return { text: 'NEEDS APPROVAL', color: 'var(--yellow)', icon: <AlertCircle size={11} /> }
  }
  return { text: 'BLOCKED', color: 'var(--red)', icon: <ShieldAlert size={11} /> }
}

export default function PolicyPreviewPanel({ preview, loading }: PolicyPreviewPanelProps) {
  if (loading) {
    return <div style={{ color: 'var(--muted)', fontSize: '12px' }}>Đang chạy mô phỏng chính sách (policy preview)...</div>
  }

  if (!preview) {
    return null
  }

  const { summary, planned_actions } = preview

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      <div style={summaryBarStyle()}>
        <div style={{ fontSize: '12px', fontWeight: 850 }}>Kết quả mô phỏng chính sách:</div>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <span style={statStyle('var(--green)')}>Auto-Allow: {summary.allow_auto}</span>
          <span style={statStyle('var(--yellow)')}>Approval Req: {summary.require_approval}</span>
          <span style={statStyle('var(--red)')}>Blocked: {summary.block}</span>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: '350px', overflowY: 'auto' }}>
        {planned_actions.map((action, idx) => {
          const badge = decisionBadge(action.decision.decision)
          const reasons = action.decision.reasons || []

          return (
            <div key={idx} style={itemStyle(action.decision.decision)}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                <div>
                  <div style={{ fontSize: '12px', fontWeight: 800 }}>{action.target_label}</div>
                  <div style={{ fontSize: '10px', color: 'var(--muted)', marginTop: '2px' }}>
                    {action.action_type} · Risk: {action.risk_tier} · Scheduled: {new Date(action.scheduled_for).toLocaleTimeString('vi-VN')}
                  </div>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '2px' }}>
                  <span style={{ fontSize: '10px', fontWeight: 800, color: badge.color, display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
                    {badge.icon} {badge.text}
                  </span>
                </div>
              </div>
              {reasons.length > 0 && (
                <div style={{ borderTop: '1px solid rgba(0,0,0,0.06)', paddingTop: '4px', marginTop: '4px', fontSize: '10px', color: badge.color }}>
                  Lý do: {reasons.join(', ')}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function summaryBarStyle(): CSSProperties {
  return {
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: '10px',
    padding: '10px 12px',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: '8px',
  }
}

function statStyle(color: string): CSSProperties {
  return {
    fontSize: '11px',
    fontWeight: 800,
    color,
    background: 'var(--card)',
    border: `1px solid ${color}`,
    borderRadius: '4px',
    padding: '2px 6px',
  }
}

function itemStyle(decision: 'allow_auto' | 'require_approval' | 'block'): CSSProperties {
  const background = decision === 'allow_auto'
    ? 'rgba(34,197,94,0.04)'
    : decision === 'require_approval'
      ? 'rgba(245,158,11,0.04)'
      : 'rgba(239,68,68,0.04)'
  const border = decision === 'allow_auto'
    ? 'rgba(34,197,94,0.15)'
    : decision === 'require_approval'
      ? 'rgba(245,158,11,0.15)'
      : 'rgba(239,68,68,0.15)'

  return {
    background,
    border: `1px solid ${border}`,
    borderRadius: '8px',
    padding: '8px 10px',
    display: 'flex',
    flexDirection: 'column',
    gap: '2px',
  }
}
