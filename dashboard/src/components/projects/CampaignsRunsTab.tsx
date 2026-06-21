/* eslint-disable @typescript-eslint/no-explicit-any, react-hooks/exhaustive-deps */
import { useState, useEffect, useCallback } from 'react'
import { Play, Eye, RefreshCw, Clock, Sparkles } from 'lucide-react'
import { fetchAPI, postAPI } from '../../api/client'
import type { Project, AffiliateCampaign } from '../../types/projects'
import PolicyPreviewPanel from './PolicyPreviewPanel'

interface CampaignsRunsTabProps {
  project: Project
  actionPending: boolean
  onMessage: (msg: string | null) => void
}

interface RunTarget {
  id: string
  target_registry_id: string
  channel_id: string | null
  status: string
  action_type: string
  risk_tier: string
  approval_status: string
}

interface PublishRun {
  id: string
  tenant_id: string
  project_id: string
  campaign_id: string | null
  created_at: string
  created_by: string
  content_item_id: string
  schedule_mode: string
  scheduled_at: string | null
  status: string
  dry_run: boolean
  autopilot_mode: string
  evidence_required: boolean
  delay_policy: Record<string, any>
  targets: RunTarget[]
}

export default function CampaignsRunsTab({
  project,
  actionPending: parentActionPending,
  onMessage,
}: CampaignsRunsTabProps) {
  const [campaigns, setCampaigns] = useState<AffiliateCampaign[]>([])
  const [runs, setRuns] = useState<PublishRun[]>([])
  const [loading, setLoading] = useState(true)
  const [actionPending, setActionPending] = useState(false)
  const [selectedCampaignId, setSelectedCampaignId] = useState<string>('')
  
  // Settings for launching runs
  const [spacingMinutes, setSpacingMinutes] = useState<number>(30)

  // Policy Preview / Launch Results
  const [previewResult, setPreviewResult] = useState<any>(null)
  const [previewLoading, setPreviewLoading] = useState(false)

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [cData, rData] = await Promise.all([
        fetchAPI<AffiliateCampaign[]>(`/api/projects/${project.id}/campaigns`),
        fetchAPI<PublishRun[]>(`/api/projects/${project.id}/runs`),
      ])
      setCampaigns(cData)
      setRuns(rData)
      if (cData.length > 0 && !selectedCampaignId) {
        setSelectedCampaignId(cData[0].id)
      }
    } catch {
      onMessage('Không tải được danh sách chiến dịch hoặc lịch sử chạy.')
    } finally {
      setLoading(false)
    }
  }, [project.id, selectedCampaignId, onMessage])

  useEffect(() => {
    loadData()
  }, [project.id])

  const handlePolicyPreview = async () => {
    if (!selectedCampaignId) return
    setPreviewLoading(true)
    setPreviewResult(null)
    try {
      const result = await postAPI<any>(
        `/api/projects/${project.id}/campaigns/${selectedCampaignId}/runs/policy-preview`,
        {
          start_at: new Date().toISOString(),
          spacing_minutes: spacingMinutes,
          input_summary: { source: 'Dashboard Cockpit Preview' },
        }
      )
      setPreviewResult(result)
      onMessage('Mô phỏng chính sách (policy preview) hoàn tất.')
    } catch (err: any) {
      const errorMsg = err?.response?.data?.detail || err?.message || 'Lỗi chạy mô phỏng.'
      onMessage(`Mô phỏng chính sách thất bại: ${errorMsg}`)
    } finally {
      setPreviewLoading(false)
    }
  }

  const handleLaunchRun = async (dryRun: boolean) => {
    if (!selectedCampaignId) return
    setActionPending(true)
    setPreviewResult(null)
    const runType = dryRun ? 'dry-run' : 'live'
    try {
      const path = `/api/projects/${project.id}/campaigns/${selectedCampaignId}/runs/${runType}`
      const payload = dryRun 
        ? {
            start_at: new Date().toISOString(),
            spacing_minutes: spacingMinutes,
            delay_policy: { min_delay_seconds: 60, max_delay_seconds: 120 },
          }
        : {
            start_at: new Date().toISOString(),
            spacing_minutes: spacingMinutes,
            delay_policy: { min_delay_seconds: 120, max_delay_seconds: 300 },
          }
      
      const result = await postAPI<any>(path, payload)
      onMessage(
        `Đã kích hoạt chạy ${dryRun ? 'DRY-RUN' : 'LIVE'}! Tạo ${result.job_count ?? 1} jobs.`
      )
      // Refresh runs list
      const rData = await fetchAPI<PublishRun[]>(`/api/projects/${project.id}/runs`)
      setRuns(rData)
    } catch (err: any) {
      const errorMsg = err?.response?.data?.detail || err?.message || 'Lỗi kích hoạt chạy.'
      onMessage(`Khởi chạy chiến dịch thất bại: ${errorMsg}`)
    } finally {
      setActionPending(false)
    }
  }

  const getCampaignName = (campaignId: string | null) => {
    if (!campaignId) return 'Chạy đơn lẻ'
    const c = campaigns.find(item => item.id === campaignId)
    return c ? c.name : 'Chiến dịch ẩn'
  }

  const getStatusStyle = (status: string) => {
    switch (status.toLowerCase()) {
      case 'posted':
      case 'completed':
      case 'success':
        return { color: 'var(--green)', bg: 'rgba(22, 163, 74, 0.08)', border: '1px solid rgba(22, 163, 74, 0.2)' }
      case 'failed':
        return { color: 'var(--red)', bg: 'rgba(220, 38, 38, 0.08)', border: '1px solid rgba(220, 38, 38, 0.2)' }
      case 'dispatching':
      case 'running':
        return { color: 'var(--accent)', bg: 'rgba(37, 99, 235, 0.08)', border: '1px solid rgba(37, 99, 235, 0.2)' }
      case 'queued':
      case 'pending':
        return { color: 'var(--yellow)', bg: 'rgba(217, 119, 6, 0.08)', border: '1px solid rgba(217, 119, 6, 0.2)' }
      case 'cancelled':
        return { color: 'var(--muted)', bg: 'rgba(100, 116, 139, 0.08)', border: '1px solid rgba(100, 116, 139, 0.2)' }
      default:
        return { color: 'var(--text)', bg: 'var(--surface)', border: '1px solid var(--border)' }
    }
  }

  if (loading) {
    return <div style={{ color: 'var(--muted)', fontSize: '12px', padding: '12px' }}>Đang tải chiến dịch & lịch sử chạy...</div>
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      
      {/* Launch Control Panel */}
      <div style={panelStyle()}>
        <div style={panelTitleStyle()}>Bảng vận hành chiến dịch</div>
        
        {campaigns.length === 0 ? (
          <div style={{ fontSize: '12px', color: 'var(--muted)', padding: '8px 0' }}>
            Chưa có chiến dịch nào được tạo cho dự án này. Hãy tạo chiến dịch trong tab "Campaign Planner".
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
              <div>
                <label style={labelStyle()}>Chọn chiến dịch:</label>
                <select
                  aria-label="Chọn chiến dịch"
                  value={selectedCampaignId}
                  onChange={e => { setSelectedCampaignId(e.target.value); setPreviewResult(null); }}
                  style={inputStyle()}
                >
                  {campaigns.map(c => (
                    <option key={c.id} value={c.id}>
                      {c.name} ({c.status.toUpperCase()})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label style={labelStyle()}>Khoảng cách bài đăng (phút):</label>
                <input
                  type="number"
                  value={spacingMinutes}
                  onChange={e => setSpacingMinutes(Math.max(1, Number(e.target.value)))}
                  style={inputStyle()}
                />
              </div>

              <div style={{ display: 'flex', alignItems: 'flex-end', gap: '6px' }}>
                <button
                  type="button"
                  disabled={previewLoading || actionPending || parentActionPending}
                  onClick={handlePolicyPreview}
                  style={buttonSecondaryStyle()}
                >
                  <Eye size={14} /> Mô phỏng
                </button>

                <button
                  type="button"
                  disabled={previewLoading || actionPending || parentActionPending}
                  onClick={() => handleLaunchRun(true)}
                  style={buttonStyle('var(--accent)')}
                >
                  <Play size={14} /> Dry-run
                </button>

                {project.live_enabled && (
                  <button
                    type="button"
                    disabled={previewLoading || actionPending || parentActionPending}
                    onClick={() => handleLaunchRun(false)}
                    style={buttonStyle('var(--green)')}
                  >
                    <Sparkles size={14} /> Live Run
                  </button>
                )}
              </div>
            </div>

            {/* Render preview inline if loaded */}
            <PolicyPreviewPanel preview={previewResult} loading={previewLoading} />
          </div>
        )}
      </div>

      {/* History of Runs */}
      <div style={panelStyle()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={panelTitleStyle()}>Lịch sử chạy (Publish Runs)</div>
          <button 
            type="button" 
            onClick={loadData}
            style={iconBtnStyle()}
            title="Làm mới danh sách"
          >
            <RefreshCw size={12} />
          </button>
        </div>

        {runs.length === 0 ? (
          <div style={{ fontSize: '12px', color: 'var(--muted)', textAlign: 'center', padding: '24px' }}>
            Dự án này chưa thực hiện lượt chạy autopilot nào.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {runs.map(run => {
              const statusStyle = getStatusStyle(run.status)
              return (
                <div key={run.id} style={runCardStyle(run.dry_run)}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px', alignItems: 'center' }}>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontWeight: 850, fontSize: '13px' }}>
                          Run #{run.id.slice(0, 8)}
                        </span>
                        <span style={run.dry_run ? dryRunPillStyle() : liveRunPillStyle()}>
                          {run.dry_run ? 'DRY-RUN' : 'LIVE'}
                        </span>
                        <span style={autopilotPillStyle()}>
                          {run.autopilot_mode.toUpperCase()}
                        </span>
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--muted)', marginTop: '4px', display: 'flex', gap: '10px', alignItems: 'center' }}>
                        <span>Chiến dịch: <strong>{getCampaignName(run.campaign_id)}</strong></span>
                        <span>•</span>
                        <span>
                          <Clock size={10} style={{ display: 'inline', marginRight: '3px' }} />
                          {new Date(run.created_at).toLocaleString('vi-VN')}
                        </span>
                      </div>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span
                        style={{
                          fontSize: '10px',
                          fontWeight: 800,
                          padding: '3px 8px',
                          borderRadius: '6px',
                          color: statusStyle.color,
                          backgroundColor: statusStyle.bg,
                          border: statusStyle.border,
                        }}
                      >
                        {run.status.toUpperCase()}
                      </span>
                    </div>
                  </div>

                  {/* Targets detailed summary */}
                  {run.targets && run.targets.length > 0 && (
                    <div style={{ marginTop: '10px', paddingTop: '8px', borderTop: '1px dashed var(--border)' }}>
                      <div style={{ fontSize: '10px', color: 'var(--muted)', fontWeight: 800, marginBottom: '6px' }}>
                        Chi tiết Target ({run.targets.length}):
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '8px' }}>
                        {run.targets.map(target => {
                          const tStatusStyle = getStatusStyle(target.status)
                          return (
                            <div key={target.id} style={targetDetailCardStyle()}>
                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <span style={{ fontWeight: 700, fontSize: '11px' }}>
                                  Target ID: {target.target_registry_id.slice(0, 8)}
                                </span>
                                <span 
                                  style={{
                                    fontSize: '9px',
                                    fontWeight: 800,
                                    padding: '1px 4px',
                                    borderRadius: '4px',
                                    color: tStatusStyle.color,
                                    backgroundColor: tStatusStyle.bg,
                                    border: tStatusStyle.border,
                                  }}
                                >
                                  {target.status.toUpperCase()}
                                </span>
                              </div>
                              <div style={{ fontSize: '9px', color: 'var(--muted)', marginTop: '2px', display: 'flex', justifyContent: 'space-between' }}>
                                <span>Action: {target.action_type} ({target.risk_tier})</span>
                                <span>Approve: {target.approval_status}</span>
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>

    </div>
  )
}

function panelStyle(): React.CSSProperties {
  return {
    background: 'var(--card)',
    border: '1px solid var(--border)',
    borderRadius: '14px',
    padding: '16px',
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
  }
}

function panelTitleStyle(): React.CSSProperties {
  return {
    fontSize: '12px',
    fontWeight: 850,
    color: 'var(--muted)',
    textTransform: 'uppercase',
    letterSpacing: '0.04em',
  }
}

function labelStyle(): React.CSSProperties {
  return {
    fontSize: '11px',
    fontWeight: 800,
    color: 'var(--muted)',
    marginBottom: '4px',
    display: 'block',
  }
}

function inputStyle(): React.CSSProperties {
  return {
    width: '100%',
    border: '1px solid var(--border)',
    background: 'var(--surface)',
    borderRadius: '10px',
    padding: '8px 12px',
    color: 'var(--text)',
    fontSize: '12px',
    outline: 'none',
  }
}

function buttonStyle(background: string): React.CSSProperties {
  return {
    border: 0,
    borderRadius: '10px',
    background,
    color: '#fff',
    padding: '8px 14px',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '6px',
    fontSize: '12px',
    fontWeight: 850,
    cursor: 'pointer',
    flex: 1,
    height: '35px',
  }
}

function buttonSecondaryStyle(): React.CSSProperties {
  return {
    border: '1px solid var(--border)',
    borderRadius: '10px',
    background: 'var(--surface)',
    color: 'var(--text)',
    padding: '8px 14px',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '6px',
    fontSize: '12px',
    fontWeight: 850,
    cursor: 'pointer',
    flex: 1,
    height: '35px',
  }
}

function iconBtnStyle(): React.CSSProperties {
  return {
    border: '1px solid var(--border)',
    background: 'var(--surface)',
    color: 'var(--muted)',
    borderRadius: '6px',
    padding: '5px',
    cursor: 'pointer',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
  }
}

function runCardStyle(dryRun: boolean): React.CSSProperties {
  return {
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderLeft: `4px solid ${dryRun ? 'var(--blue)' : 'var(--purple)'}`,
    borderRadius: '10px',
    padding: '12px',
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  }
}

function dryRunPillStyle(): React.CSSProperties {
  return {
    padding: '1px 5px',
    borderRadius: '4px',
    background: 'rgba(37, 99, 235, 0.08)',
    border: '1px solid rgba(37, 99, 235, 0.25)',
    color: 'var(--blue)',
    fontSize: '9px',
    fontWeight: 800,
  }
}

function liveRunPillStyle(): React.CSSProperties {
  return {
    padding: '1px 5px',
    borderRadius: '4px',
    background: 'rgba(124, 58, 237, 0.08)',
    border: '1px solid rgba(124, 58, 237, 0.25)',
    color: 'var(--purple)',
    fontSize: '9px',
    fontWeight: 800,
  }
}

function autopilotPillStyle(): React.CSSProperties {
  return {
    padding: '1px 5px',
    borderRadius: '4px',
    background: 'rgba(100, 116, 139, 0.08)',
    border: '1px solid rgba(100, 116, 139, 0.2)',
    color: 'var(--muted)',
    fontSize: '9px',
    fontWeight: 800,
  }
}

function targetDetailCardStyle(): React.CSSProperties {
  return {
    background: 'var(--card)',
    border: '1px solid var(--border)',
    borderRadius: '8px',
    padding: '6px 8px',
    display: 'flex',
    flexDirection: 'column',
  }
}
