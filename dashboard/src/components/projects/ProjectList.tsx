import type { CSSProperties } from 'react'
import { Folder, Play, Pause, Archive, ShieldAlert, ShieldCheck } from 'lucide-react'
import type { Project } from '../../types/projects'

interface ProjectListProps {
  projects: Project[]
  loading: boolean
  onToggleKillSwitch: (projectId: string, enable: boolean) => void
  onTogglePause: (projectId: string, pause: boolean) => void
  onArchive: (projectId: string) => void
  onSelectProject: (projectId: string) => void
  selectedProjectId: string | null
}

export default function ProjectList({
  projects,
  loading,
  onToggleKillSwitch,
  onTogglePause,
  onArchive,
  onSelectProject,
  selectedProjectId,
}: ProjectListProps) {
  if (loading) {
    return <div style={{ color: 'var(--muted)', fontSize: '12px' }}>Đang tải danh sách dự án...</div>
  }

  if (projects.length === 0) {
    return <div style={{ color: 'var(--muted)', fontSize: '12px', textAlign: 'center', padding: '20px' }}>Chưa có dự án nào được cấu hình.</div>
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
      {projects.map(project => {
        const isSelected = selectedProjectId === project.id
        const isPaused = project.status === 'paused'
        const isArchived = project.status === 'archived'

        return (
          <div
            key={project.id}
            onClick={() => onSelectProject(project.id)}
            style={{
              ...itemStyle(isSelected),
              borderLeft: `4px solid ${project.kill_switch_enabled ? 'var(--red)' : isPaused ? 'var(--yellow)' : 'var(--green)'}`,
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', alignItems: 'flex-start', flexWrap: 'wrap' }}>
              <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                <Folder size={18} style={{ color: isPaused ? 'var(--yellow)' : 'var(--blue)' }} />
                <div>
                  <div style={{ fontSize: '13px', fontWeight: 800 }}>{project.name}</div>
                  <div style={{ fontSize: '10px', color: 'var(--muted)', display: 'flex', gap: '6px', marginTop: '2px' }}>
                    {project.niche && <span style={badgeStyle()}>{project.niche.toUpperCase()}</span>}
                    <span>{project.default_autopilot_mode.replace('_', ' ').toUpperCase()}</span>
                  </div>
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                {project.kill_switch_enabled ? (
                  <span style={pillStyle('var(--red)')}><ShieldAlert size={10} /> KS ACTIVE</span>
                ) : (
                  <span style={pillStyle(isPaused ? 'var(--yellow)' : 'var(--green)')}>
                    {project.status.toUpperCase()}
                  </span>
                )}
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', alignItems: 'center', fontSize: '11px', color: 'var(--muted)', borderTop: '1px solid var(--border)', paddingTop: '8px', marginTop: '4px' }}>
              <div style={{ display: 'flex', gap: '8px' }}>
                <span>Live flag: {project.live_enabled ? 'ON - LOCKED' : 'OFF'}</span>
                <span>Dry-run: {project.dry_run_required ? 'REQ' : 'OPT'}</span>
              </div>
              
              <div style={{ display: 'flex', gap: '6px' }} onClick={e => e.stopPropagation()}>
                <button
                  type="button"
                  onClick={() => onToggleKillSwitch(project.id, !project.kill_switch_enabled)}
                  style={{
                    ...actionBtnStyle(project.kill_switch_enabled ? '#10b981' : '#ef4444'),
                    padding: '3px 6px',
                  }}
                >
                  {project.kill_switch_enabled ? <ShieldCheck size={11} /> : <ShieldAlert size={11} />}
                  {project.kill_switch_enabled ? 'CLEAR KS' : 'KILL SWITCH'}
                </button>
                {!isArchived && (
                  <>
                    <button
                      type="button"
                      onClick={() => onTogglePause(project.id, !isPaused)}
                      style={actionBtnStyle('var(--muted)')}
                      title={isPaused ? 'Tiếp tục dự án' : 'Tạm dừng dự án'}
                    >
                      {isPaused ? <Play size={11} /> : <Pause size={11} />}
                    </button>
                    <button
                      type="button"
                      onClick={() => onArchive(project.id)}
                      style={actionBtnStyle('var(--muted)')}
                      title="Lưu trữ dự án"
                    >
                      <Archive size={11} />
                    </button>
                  </>
                )}
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

function itemStyle(selected: boolean): CSSProperties {
  return {
    background: selected ? 'rgba(59,130,246,0.06)' : 'var(--card)',
    border: `1px solid ${selected ? 'var(--accent)' : 'var(--border)'}`,
    borderRadius: '10px',
    padding: '12px',
    cursor: 'pointer',
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
    transition: 'all 0.15s ease',
  }
}

function badgeStyle(): CSSProperties {
  return {
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: '4px',
    padding: '1px 4px',
    fontSize: '9px',
    fontWeight: 700,
  }
}

function pillStyle(color: string): CSSProperties {
  return {
    padding: '2px 6px',
    borderRadius: '4px',
    background: 'var(--surface)',
    border: `1px solid ${color}`,
    color,
    fontSize: '9px',
    fontWeight: 800,
    display: 'inline-flex',
    alignItems: 'center',
    gap: '3px',
  }
}

function actionBtnStyle(color: string): CSSProperties {
  return {
    border: `1px solid var(--border)`,
    background: 'var(--surface)',
    color,
    borderRadius: '6px',
    padding: '4px',
    cursor: 'pointer',
    display: 'inline-flex',
    alignItems: 'center',
    gap: '4px',
    fontSize: '10px',
    fontWeight: 800,
  }
}
