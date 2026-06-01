import { useState, useEffect, useCallback } from 'react'
import { Plus, ShieldAlert, FolderOpen, UserPlus } from 'lucide-react'
import { fetchAPI, postAPI, patchAPI } from '../api/client'
import ProjectList from '../components/projects/ProjectList'
import TargetRegistryList from '../components/projects/TargetRegistryList'
import type { Project, TargetRegistry } from '../types/projects'
import type { SocialChannel } from '../types'

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([])
  const [targets, setTargets] = useState<TargetRegistry[]>([])
  const [channels, setChannels] = useState<SocialChannel[]>([])
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null)
  
  const [loadingProjects, setLoadingProjects] = useState(true)
  const [loadingTargets, setLoadingTargets] = useState(false)
  const [actionPending, setActionPending] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  // Form states for project creation
  const [newProjectName, setNewProjectName] = useState('')
  const [newProjectNiche, setNewProjectNiche] = useState('')
  const [newProjectLive, setNewProjectLive] = useState(false)
  const [newProjectDryRun, setNewProjectDryRun] = useState(true)
  const [newProjectAutopilot, setNewProjectAutopilot] = useState<Project['default_autopilot_mode']>('guarded_autopilot')

  // Form states for target registration
  const [newTargetLabel, setNewTargetLabel] = useState('')
  const [newTargetChannelId, setNewTargetChannelId] = useState('')

  const loadProjects = useCallback(async () => {
    setLoadingProjects(true)
    try {
      const data = await fetchAPI<Project[]>('/api/projects')
      setProjects(data)
      if (data.length > 0 && !selectedProjectId) {
        setSelectedProjectId(data[0].id)
      }
    } catch {
      setMessage('Không tải được danh sách dự án.')
    } finally {
      setLoadingProjects(false)
    }
  }, [selectedProjectId])

  const loadTargets = useCallback(async (projectId: string) => {
    setLoadingTargets(true)
    try {
      const data = await fetchAPI<TargetRegistry[]>(`/api/projects/${projectId}/targets`)
      setTargets(data)
    } catch {
      setMessage('Không tải được danh sách target đăng ký.')
    } finally {
      setLoadingTargets(false)
    }
  }, [])

  const loadChannels = useCallback(async () => {
    try {
      const data = await fetchAPI<SocialChannel[]>('/api/channels')
      setChannels(data)
    } catch {
      setMessage('Không tải được danh sách kênh liên kết.')
    }
  }, [])

  useEffect(() => {
    loadProjects()
    loadChannels()
  }, [loadProjects, loadChannels])

  useEffect(() => {
    if (selectedProjectId) {
      loadTargets(selectedProjectId)
    } else {
      setTargets([])
    }
  }, [selectedProjectId, loadTargets])

  const selectedProject = projects.find(p => p.id === selectedProjectId) || null

  const handleCreateProject = async () => {
    const name = newProjectName.trim()
    if (!name) {
      setMessage('Vui lòng nhập tên dự án.')
      return
    }
    setActionPending(true)
    try {
      const created = await postAPI<Project>('/api/projects', {
        name,
        niche: newProjectNiche.trim() || null,
        live_enabled: newProjectLive,
        dry_run_required: newProjectDryRun,
        default_autopilot_mode: newProjectAutopilot,
        allowed_target_types: ['fanpage'],
      })
      setProjects(prev => [created, ...prev])
      setSelectedProjectId(created.id)
      setNewProjectName('')
      setNewProjectNiche('')
      setMessage(`Đã tạo dự án mới: ${created.name}`)
    } catch {
      setMessage('Không tạo được dự án mới.')
    } finally {
      setActionPending(false)
    }
  }

  const handleToggleKillSwitch = async (projectId: string, enable: boolean) => {
    setActionPending(true)
    try {
      const path = enable 
        ? `/api/projects/${projectId}/kill-switch`
        : `/api/projects/${projectId}/kill-switch/clear`
      const updated = await postAPI<Project>(path)
      setProjects(prev => prev.map(p => p.id === projectId ? updated : p))
      setMessage(enable ? 'Đã KÍCH HOẠT KILL SWITCH cho dự án.' : 'Đã TẮT/XÓA KILL SWITCH thành công.')
    } catch {
      setMessage('Không cập nhật được trạng thái Kill Switch.')
    } finally {
      setActionPending(false)
    }
  }

  const handleTogglePause = async (projectId: string, pause: boolean) => {
    setActionPending(true)
    try {
      const path = pause 
        ? `/api/projects/${projectId}/pause`
        : `/api/projects/${projectId}`
      
      let updated: Project
      if (pause) {
        updated = await postAPI<Project>(path)
      } else {
        updated = await patchAPI<Project>(path, { status: 'active' })
      }
      
      setProjects(prev => prev.map(p => p.id === projectId ? updated : p))
      setMessage(pause ? 'Đã tạm dừng hoạt động dự án.' : 'Đã kích hoạt lại dự án.')
    } catch {
      setMessage('Không cập nhật được trạng thái dự án.')
    } finally {
      setActionPending(false)
    }
  }

  const handleArchive = async (projectId: string) => {
    setActionPending(true)
    try {
      const updated = await postAPI<Project>(`/api/projects/${projectId}/archive`)
      setProjects(prev => prev.map(p => p.id === projectId ? updated : p))
      setMessage('Đã lưu trữ (archive) dự án.')
    } catch {
      setMessage('Không lưu trữ được dự án.')
    } finally {
      setActionPending(false)
    }
  }

  const handleRegisterTarget = async () => {
    const label = newTargetLabel.trim()
    if (!selectedProjectId) return
    if (!label || !newTargetChannelId) {
      setMessage('Vui lòng điền nhãn target và chọn kênh liên kết.')
      return
    }
    setActionPending(true)
    try {
      const created = await postAPI<TargetRegistry>(`/api/projects/${selectedProjectId}/targets`, {
        target_type: 'fanpage',
        social_channel_id: newTargetChannelId,
        label,
      })
      setTargets(prev => [created, ...prev])
      setNewTargetLabel('')
      setNewTargetChannelId('')
      setMessage(`Đã đăng ký target: ${created.label}`)
    } catch {
      setMessage('Không đăng ký được target.')
    } finally {
      setActionPending(false)
    }
  }

  const handleToggleTargetStatus = async (targetId: string, pause: boolean) => {
    if (!selectedProjectId) return
    setActionPending(true)
    try {
      const path = pause 
        ? `/api/projects/${selectedProjectId}/targets/${targetId}/pause`
        : `/api/projects/${selectedProjectId}/targets/${targetId}`
      
      let updated: TargetRegistry
      if (pause) {
        updated = await postAPI<TargetRegistry>(path)
      } else {
        updated = await patchAPI<TargetRegistry>(path, { status: 'active' })
      }
      
      setTargets(prev => prev.map(t => t.id === targetId ? updated : t))
      setMessage(pause ? 'Đã tạm dừng target.' : 'Đã kích hoạt lại target.')
    } catch {
      setMessage('Không cập nhật được trạng thái target.')
    } finally {
      setActionPending(false)
    }
  }

  const handleBlockTarget = async (targetId: string) => {
    if (!selectedProjectId) return
    setActionPending(true)
    try {
      const updated = await postAPI<TargetRegistry>(`/api/projects/${selectedProjectId}/targets/${targetId}/block`)
      setTargets(prev => prev.map(t => t.id === targetId ? updated : t))
      setMessage('Đã khóa (block) target thành công.')
    } catch {
      setMessage('Không khóa được target.')
    } finally {
      setActionPending(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div>
        <div style={{ fontSize: '22px', fontWeight: 850 }}>Quản lý dự án & Autopilot Policy</div>
        <div style={{ fontSize: '12px', color: 'var(--muted)' }}>Cấu hình ranh giới chính sách (policy boundary) và đăng ký targets an toàn cho Affiliate.</div>
      </div>

      {message && <div style={messageStyle()}>{message}</div>}

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(280px, 1fr) minmax(320px, 1.8fr)', gap: '16px', alignItems: 'start' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <section style={panelStyle()}>
            <div style={{ fontSize: '13px', fontWeight: 850, marginBottom: '10px' }}>Danh sách dự án</div>
            <ProjectList
              projects={projects}
              loading={loadingProjects}
              onToggleKillSwitch={handleToggleKillSwitch}
              onTogglePause={handleTogglePause}
              onArchive={handleArchive}
              onSelectProject={setSelectedProjectId}
              selectedProjectId={selectedProjectId}
            />
          </section>

          <section style={panelStyle()}>
            <div style={{ fontSize: '13px', fontWeight: 850, marginBottom: '10px' }}>+ Tạo dự án mới</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <input value={newProjectName} onChange={e => setNewProjectName(e.target.value)} placeholder="Tên dự án (Ví dụ: Affiliate Gadgets)" style={inputStyle()} />
              <input value={newProjectNiche} onChange={e => setNewProjectNiche(e.target.value)} placeholder="Niche (Ví dụ: beauty, tech)" style={inputStyle()} />
              
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '11px', color: 'var(--muted)', margin: '4px 0' }}>
                <label style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                  <input type="checkbox" checked={newProjectLive} onChange={e => setNewProjectLive(e.target.checked)} />
                  Kích hoạt Live Mutation (Live run)
                </label>
                <label style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                  <input type="checkbox" checked={newProjectDryRun} onChange={e => setNewProjectDryRun(e.target.checked)} />
                  Bắt buộc Dry-run trước khi Live
                </label>
              </div>

              <select 
                aria-label="Autopilot Mode"
                value={newProjectAutopilot} 
                onChange={e => setNewProjectAutopilot(e.target.value as Project['default_autopilot_mode'])} 
                style={inputStyle()}
              >
                <option value="draft">DRAFT</option>
                <option value="assisted">ASSISTED</option>
                <option value="guarded_autopilot">GUARDED AUTOPILOT</option>
                <option value="manual_required">MANUAL REQUIRED</option>
              </select>

              <button 
                type="button" 
                onClick={handleCreateProject} 
                disabled={actionPending}
                style={buttonStyle('#2563eb')}
              >
                <Plus size={14} /> TẠO DỰ ÁN
              </button>
            </div>
          </section>
        </div>

        {selectedProject ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <section style={panelStyle()}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', alignItems: 'center', flexWrap: 'wrap', borderBottom: '1px solid var(--border)', paddingBottom: '12px' }}>
                <div>
                  <div style={{ fontSize: '11px', color: 'var(--muted)' }}>Chi tiết dự án</div>
                  <div style={{ fontSize: '18px', fontWeight: 850 }}>{selectedProject.name}</div>
                </div>
                {selectedProject.kill_switch_enabled && (
                  <span style={ksPillStyle()}>
                    <ShieldAlert size={14} /> KILL SWITCH ĐANG BẬT
                  </span>
                )}
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginTop: '12px', fontSize: '12px' }}>
                <div>
                  <div style={{ color: 'var(--muted)', fontWeight: 800 }}>Chính sách Autopilot</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginTop: '6px' }}>
                    <div>Live Actions: <strong>{selectedProject.live_enabled ? 'CHO PHÉP' : 'TẮT (CHỈ DRY-RUN)'}</strong></div>
                    <div>Yêu cầu Dry-run: <strong>{selectedProject.dry_run_required ? 'BẮT BUỘC' : 'TÙY CHỌN'}</strong></div>
                    <div>Autopilot Mode: <strong>{selectedProject.default_autopilot_mode.toUpperCase()}</strong></div>
                  </div>
                </div>
                <div>
                  <div style={{ color: 'var(--muted)', fontWeight: 800 }}>Niche / Phân loại</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginTop: '6px' }}>
                    <div>Niche: <strong>{selectedProject.niche || 'CHƯA PHÂN LOẠI'}</strong></div>
                    <div>Trạng thái: <strong>{selectedProject.status.toUpperCase()}</strong></div>
                    <div>Allowed Targets: <strong>{selectedProject.allowed_target_types.join(', ').toUpperCase()}</strong></div>
                  </div>
                </div>
              </div>
            </section>

            <section style={panelStyle()}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                <div style={{ fontSize: '13px', fontWeight: 850 }}>Đăng ký Targets dự án</div>
                <div style={{ fontSize: '11px', color: 'var(--muted)' }}>Tổng: {targets.length} targets</div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'minmax(240px, 1.4fr) minmax(200px, 1fr)', gap: '14px', alignItems: 'start' }}>
                <TargetRegistryList
                  targets={targets}
                  loading={loadingTargets}
                  onToggleStatus={handleToggleTargetStatus}
                  onBlockTarget={handleBlockTarget}
                />

                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '12px', padding: '12px' }}>
                  <div style={{ fontSize: '11px', color: 'var(--muted)', fontWeight: 850 }}><UserPlus size={12} style={{ display: 'inline', marginRight: '4px' }} /> Đăng ký Target mới</div>
                  
                  <input value={newTargetLabel} onChange={e => setNewTargetLabel(e.target.value)} placeholder="Nhãn Target (ví dụ: Fanpage Beauty A)" style={inputStyle()} />
                  
                  <select 
                    aria-label="Kênh liên kết"
                    value={newTargetChannelId} 
                    onChange={e => setNewTargetChannelId(e.target.value)} 
                    style={inputStyle()}
                  >
                    <option value="">-- Chọn kênh Facebook --</option>
                    {channels.map(channel => (
                      <option key={channel.id} value={channel.id}>
                        {channel.display_name} ({channel.platform} / {channel.channel_type})
                      </option>
                    ))}
                  </select>

                  <button 
                    type="button" 
                    onClick={handleRegisterTarget} 
                    disabled={actionPending}
                    style={buttonStyle('#16a34a')}
                  >
                    + ĐĂNG KÝ TARGET
                  </button>
                </div>
              </div>
            </section>
          </div>
        ) : (
          <div style={emptyPanelStyle()}>
            <FolderOpen size={48} color="var(--muted)" />
            <div style={{ fontSize: '14px', fontWeight: 700 }}>Chọn một dự án để xem cấu hình</div>
            <div style={{ fontSize: '12px', color: 'var(--muted)' }}>Tạo dự án mới hoặc chọn dự án từ danh sách bên trái.</div>
          </div>
        )}
      </div>
    </div>
  )
}

function panelStyle(): React.CSSProperties {
  return { background: 'var(--card)', border: '1px solid var(--border)', borderRadius: '14px', padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }
}

function inputStyle(): React.CSSProperties {
  return { width: '100%', border: '1px solid var(--border)', background: 'var(--surface)', borderRadius: '10px', padding: '8px 12px', color: 'var(--text)', fontSize: '12px', outline: 'none' }
}

function buttonStyle(background: string): React.CSSProperties {
  return { border: 0, borderRadius: '10px', background, color: '#fff', padding: '8px 14px', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: '6px', fontSize: '12px', fontWeight: 850, cursor: 'pointer' }
}

function messageStyle(): React.CSSProperties {
  return { padding: '12px', borderRadius: '12px', background: 'rgba(37,99,235,0.08)', border: '1px solid rgba(37,99,235,0.25)', color: 'var(--accent)', fontSize: '12px' }
}

function ksPillStyle(): React.CSSProperties {
  return {
    padding: '4px 10px',
    borderRadius: '6px',
    background: 'rgba(239, 68, 68, 0.12)',
    border: '1px solid rgba(239, 68, 68, 0.3)',
    color: 'var(--red)',
    fontSize: '11px',
    fontWeight: 800,
    display: 'inline-flex',
    alignItems: 'center',
    gap: '6px',
  }
}

function emptyPanelStyle(): React.CSSProperties {
  return {
    background: 'var(--card)',
    border: '1px solid var(--border)',
    borderRadius: '14px',
    padding: '40px',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '12px',
    minHeight: '280px',
  }
}
