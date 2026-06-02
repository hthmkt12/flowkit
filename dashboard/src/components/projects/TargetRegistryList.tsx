import type { CSSProperties } from 'react'
import { CheckCircle, AlertTriangle, Shield, Pause, Play } from 'lucide-react'
import type { TargetRegistry } from '../../types/projects'

interface TargetRegistryListProps {
  targets: TargetRegistry[]
  loading: boolean
  onToggleStatus: (targetId: string, pause: boolean) => void
  onBlockTarget: (targetId: string) => void
}

function readinessLabel(readiness: string) {
  if (readiness === 'ready') return { text: 'READY', color: 'var(--green)' }
  if (readiness === 'offline') return { text: 'OFFLINE', color: 'var(--red)' }
  if (readiness === 'checkpoint') return { text: 'CHECKPOINT', color: 'var(--yellow)' }
  if (readiness === 'logged_out') return { text: 'LOGGED OUT', color: 'var(--red)' }
  return { text: 'UNKNOWN', color: 'var(--muted)' }
}

export default function TargetRegistryList({
  targets,
  loading,
  onToggleStatus,
  onBlockTarget,
}: TargetRegistryListProps) {
  if (loading) {
    return <div style={{ color: 'var(--muted)', fontSize: '12px' }}>Đang tải danh sách targets...</div>
  }

  if (targets.length === 0) {
    return <div style={{ color: 'var(--muted)', fontSize: '12px', textAlign: 'center', padding: '20px' }}>Chưa có target nào được đăng ký dưới dự án này.</div>
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      {targets.map(target => {
        const isPaused = target.status === 'paused'
        const isBlocked = target.status === 'blocked'
        const readDetail = readinessLabel(target.readiness)

        return (
          <div
            key={target.id}
            style={{
              ...itemStyle(),
              opacity: isBlocked ? 0.6 : 1,
              borderLeft: `4px solid ${isBlocked ? 'var(--red)' : isPaused ? 'var(--yellow)' : 'var(--blue)'}`,
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ fontSize: '12px', fontWeight: 850 }}>{target.label}</span>
                  <span style={pillStyle(isBlocked ? 'var(--red)' : isPaused ? 'var(--yellow)' : 'var(--blue)')}>
                    {target.target_type.toUpperCase()}
                  </span>
                </div>
                <div style={{ fontSize: '10px', color: 'var(--muted)', marginTop: '2px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                  <span>Platform: {target.platform}</span>
                  {target.rules && target.rules.cooldown_minutes !== undefined && (
                    <span>Cooldown: {String(target.rules.cooldown_minutes)}m</span>
                  )}
                  {target.rules && target.rules.max_posts_per_day !== undefined && (
                    <span>Daily Max: {String(target.rules.max_posts_per_day)}</span>
                  )}
                  {target.last_seen_at && <span>Seen: {new Date(target.last_seen_at).toLocaleTimeString('vi-VN')}</span>}
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '2px' }}>
                  <span style={{ fontSize: '10px', fontWeight: 800, color: readDetail.color, display: 'inline-flex', alignItems: 'center', gap: '2px' }}>
                    {target.readiness === 'ready' ? <CheckCircle size={10} /> : <AlertTriangle size={10} />}
                    {readDetail.text}
                  </span>
                  <span style={{ fontSize: '9px', color: 'var(--muted)' }}>Status: {target.status}</span>
                </div>

                <div style={{ display: 'flex', gap: '4px' }}>
                  {!isBlocked && (
                    <button
                      type="button"
                      onClick={() => onToggleStatus(target.id, !isPaused)}
                      style={actionBtnStyle(isPaused ? 'var(--green)' : 'var(--yellow)')}
                      title={isPaused ? 'Kích hoạt target' : 'Tạm dừng target'}
                    >
                      {isPaused ? <Play size={11} /> : <Pause size={11} />}
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => onBlockTarget(target.id)}
                    style={actionBtnStyle('var(--red)')}
                    title={isBlocked ? 'Bỏ block target' : 'Block target'}
                  >
                    {isBlocked ? <Play size={11} /> : <Shield size={11} />}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

function itemStyle(): CSSProperties {
  return {
    background: 'var(--card)',
    border: '1px solid var(--border)',
    borderRadius: '10px',
    padding: '10px 12px',
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  }
}

function pillStyle(color: string): CSSProperties {
  return {
    padding: '1px 4px',
    borderRadius: '4px',
    background: 'var(--surface)',
    border: `1px solid ${color}`,
    color,
    fontSize: '8px',
    fontWeight: 800,
  }
}

function actionBtnStyle(color: string): CSSProperties {
  return {
    border: '1px solid var(--border)',
    background: 'var(--surface)',
    color,
    borderRadius: '6px',
    padding: '4px',
    cursor: 'pointer',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
  }
}
