import type { CSSProperties } from 'react'
import { ShieldAlert, Play, Pause, Archive } from 'lucide-react'
import type { Project } from '../../types/projects'

interface OverviewPolicyTabProps {
  project: Project
  actionPending: boolean
  onToggleKillSwitch: (projectId: string, enable: boolean) => Promise<void>
  onTogglePause: (projectId: string, pause: boolean) => Promise<void>
  onArchive: (projectId: string) => Promise<void>
}

export default function OverviewPolicyTab({
  project,
  actionPending,
  onToggleKillSwitch,
  onTogglePause,
  onArchive,
}: OverviewPolicyTabProps) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* Policy and Niche Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '14px' }}>
        
        {/* Autopilot Policy Panel */}
        <div style={panelStyle()}>
          <div style={panelTitleStyle()}>Chính Sách Autopilot</div>
          <div style={policyRowStyle()}>
            <span style={policyLabelStyle()}>Live Posting:</span>
            <span style={project.live_enabled ? activeStatusStyle() : inactiveStatusStyle()}>
              {project.live_enabled ? 'CHO PHÉP' : 'TẮT (CHỈ DRY-RUN)'}
            </span>
          </div>
          <div style={policyRowStyle()}>
            <span style={policyLabelStyle()}>Yêu cầu Dry-run:</span>
            <span style={project.dry_run_required ? activeStatusStyle() : inactiveStatusStyle()}>
              {project.dry_run_required ? 'BẮT BUỘC' : 'TÙY CHỌN'}
            </span>
          </div>
          <div style={policyRowStyle()}>
            <span style={policyLabelStyle()}>Autopilot Mode:</span>
            <span style={highlightTextStyle()}>{project.default_autopilot_mode.toUpperCase()}</span>
          </div>
        </div>

        {/* Niche & Meta Info Panel */}
        <div style={panelStyle()}>
          <div style={panelTitleStyle()}>Thông Tin Phân Loại</div>
          <div style={policyRowStyle()}>
            <span style={policyLabelStyle()}>Chủ đề (Niche):</span>
            <span style={highlightTextStyle()}>{project.niche || 'CHƯA PHÂN LOẠI'}</span>
          </div>
          <div style={policyRowStyle()}>
            <span style={policyLabelStyle()}>Trạng thái:</span>
            <span style={project.status === 'active' ? activeStatusStyle() : inactiveStatusStyle()}>
              {project.status.toUpperCase()}
            </span>
          </div>
          <div style={policyRowStyle()}>
            <span style={policyLabelStyle()}>Allowed Targets:</span>
            <span style={highlightTextStyle()}>{project.allowed_target_types.join(', ').toUpperCase()}</span>
          </div>
        </div>

      </div>

      {/* Operator Safety Controls */}
      <div style={panelStyle()}>
        <div style={panelTitleStyle()}>Bảng Điều Khiển An Toàn (Safety Controls)</div>
        <p style={descStyle()}>
          Các tác vụ autopilot của dự án này hoạt động nghiêm ngặt trong ranh giới chính sách trên. Hãy sử dụng các điều khiển khẩn cấp dưới đây nếu phát hiện bất thường từ Agent.
        </p>

        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', marginTop: '6px' }}>
          {/* Kill Switch Toggle */}
          <button
            type="button"
            disabled={actionPending}
            onClick={() => onToggleKillSwitch(project.id, !project.kill_switch_enabled)}
            style={project.kill_switch_enabled ? buttonDangerStyle() : buttonSecondaryStyle()}
          >
            <ShieldAlert size={15} />
            {project.kill_switch_enabled ? 'TẮT EMERGENCY KILL SWITCH' : 'KÍCH HOẠT EMERGENCY KILL SWITCH'}
          </button>

          {/* Pause / Resume Toggle */}
          <button
            type="button"
            disabled={actionPending}
            onClick={() => onTogglePause(project.id, project.status === 'active')}
            style={buttonSecondaryStyle()}
          >
            {project.status === 'active' ? (
              <>
                <Pause size={15} /> TẠM DỪNG DỰ ÁN
              </>
            ) : (
              <>
                <Play size={15} /> KÍCH HOẠT LẠI DỰ ÁN
              </>
            )}
          </button>

          {/* Archive Project */}
          {project.status !== 'archived' && (
            <button
              type="button"
              disabled={actionPending}
              onClick={() => onArchive(project.id)}
              style={buttonOutlineStyle()}
            >
              <Archive size={15} /> LƯU TRỮ DỰ ÁN (ARCHIVE)
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

function panelStyle(): CSSProperties {
  return {
    background: 'var(--card)',
    border: '1px solid var(--border)',
    borderRadius: '14px',
    padding: '16px',
    display: 'flex',
    flexDirection: 'column',
    gap: '10px',
  }
}

function panelTitleStyle(): CSSProperties {
  return {
    fontSize: '12px',
    fontWeight: 850,
    color: 'var(--muted)',
    textTransform: 'uppercase',
    letterSpacing: '0.04em',
    borderBottom: '1px solid var(--border)',
    paddingBottom: '8px',
    marginBottom: '4px',
  }
}

function policyRowStyle(): CSSProperties {
  return {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: '13px',
    padding: '4px 0',
  }
}

function policyLabelStyle(): CSSProperties {
  return {
    color: 'var(--muted)',
    fontWeight: 500,
  }
}

function highlightTextStyle(): CSSProperties {
  return {
    color: 'var(--text)',
    fontWeight: 700,
  }
}

function activeStatusStyle(): CSSProperties {
  return {
    color: 'var(--green)',
    fontWeight: 800,
  }
}

function inactiveStatusStyle(): CSSProperties {
  return {
    color: 'var(--red)',
    fontWeight: 800,
  }
}

function descStyle(): CSSProperties {
  return {
    fontSize: '12px',
    color: 'var(--muted)',
    lineHeight: 1.5,
    margin: 0,
  }
}

function buttonDangerStyle(): CSSProperties {
  return {
    border: '1px solid rgba(239, 68, 68, 0.4)',
    borderRadius: '10px',
    background: '#ef4444',
    color: '#fff',
    padding: '9px 16px',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '8px',
    fontSize: '12px',
    fontWeight: 800,
    cursor: 'pointer',
    transition: 'all 0.15s ease',
  }
}

function buttonSecondaryStyle(): CSSProperties {
  return {
    border: '1px solid var(--border)',
    borderRadius: '10px',
    background: 'var(--surface)',
    color: 'var(--text)',
    padding: '9px 16px',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '8px',
    fontSize: '12px',
    fontWeight: 800,
    cursor: 'pointer',
    transition: 'all 0.15s ease',
  }
}

function buttonOutlineStyle(): CSSProperties {
  return {
    border: '1px solid rgba(239, 68, 68, 0.25)',
    borderRadius: '10px',
    background: 'transparent',
    color: 'var(--red)',
    padding: '9px 16px',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '8px',
    fontSize: '12px',
    fontWeight: 800,
    cursor: 'pointer',
    transition: 'all 0.15s ease',
  }
}
