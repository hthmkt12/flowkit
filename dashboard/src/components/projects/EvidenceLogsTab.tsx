import { useState, useEffect, useCallback } from 'react'
import { FileText, Camera, RefreshCw, AlertCircle, ExternalLink } from 'lucide-react'
import { fetchAPI, postAPI } from '../../api/client'
import type { Project, RunEvidence } from '../../types/projects'

interface EvidenceLogsTabProps {
  project: Project
  onMessage: (msg: string | null) => void
}

interface PublishRunMin {
  id: string
  campaign_id: string | null
  created_at: string
  dry_run: boolean
  status: string
}

export default function EvidenceLogsTab({
  project,
  onMessage,
}: EvidenceLogsTabProps) {
  const [runs, setRuns] = useState<PublishRunMin[]>([])
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const [evidence, setEvidence] = useState<RunEvidence | null>(null)
  
  const [loadingRuns, setLoadingRuns] = useState(true)
  const [loadingEvidence, setLoadingEvidence] = useState(false)
  const [actionPending, setActionPending] = useState(false)

  const loadRuns = useCallback(async () => {
    setLoadingRuns(true)
    try {
      const data = await fetchAPI<PublishRunMin[]>(`/api/projects/${project.id}/runs`)
      setRuns(data)
      if (data.length > 0 && !selectedRunId) {
        setSelectedRunId(data[0].id)
      }
    } catch {
      onMessage('Không tải được danh sách lượt chạy để xem bằng chứng.')
    } finally {
      setLoadingRuns(false)
    }
  }, [project.id, selectedRunId, onMessage])

  const loadEvidence = useCallback(async (runId: string) => {
    setLoadingEvidence(true)
    setEvidence(null)
    try {
      const data = await fetchAPI<RunEvidence>(`/api/projects/${project.id}/runs/${runId}/evidence`)
      setEvidence(data)
    } catch (err: any) {
      // Evidence endpoint returns 404 if no evidence summary exists yet, which is fine
      console.log('No evidence loaded yet', err)
      setEvidence(null)
    } finally {
      setLoadingEvidence(false)
    }
  }, [project.id])

  useEffect(() => {
    loadRuns()
  }, [project.id])

  useEffect(() => {
    if (selectedRunId) {
      loadEvidence(selectedRunId)
    } else {
      setEvidence(null)
    }
  }, [selectedRunId, loadEvidence])

  const handleRefreshEvidence = async () => {
    if (!selectedRunId) return
    setActionPending(true)
    try {
      const result = await postAPI<RunEvidence>(
        `/api/projects/${project.id}/runs/${selectedRunId}/evidence/refresh`,
        { artifact_refs: [] }
      )
      setEvidence(result)
      onMessage('Đã thu thập và làm mới bằng chứng thành công!')
    } catch (err: any) {
      const errorMsg = err?.response?.data?.detail || err?.message || 'Lỗi làm mới bằng chứng.'
      onMessage(`Thu thập bằng chứng thất bại: ${errorMsg}`)
    } finally {
      setActionPending(false)
    }
  }

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'posted':
      case 'completed':
      case 'success':
        return 'var(--green)'
      case 'failed':
        return 'var(--red)'
      case 'queued':
      case 'pending':
        return 'var(--yellow)'
      default:
        return 'var(--muted)'
    }
  }

  if (loadingRuns) {
    return <div style={{ color: 'var(--muted)', fontSize: '12px', padding: '12px' }}>Đang tải danh sách bằng chứng...</div>
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '250px 1fr', gap: '16px', alignItems: 'start' }}>
      
      {/* Run selector list */}
      <div style={panelStyle()}>
        <div style={panelTitleStyle()}>Chọn lượt chạy (Runs)</div>
        {runs.length === 0 ? (
          <div style={{ fontSize: '11px', color: 'var(--muted)', textAlign: 'center', padding: '12px 0' }}>
            Chưa có lượt chạy autopilot nào.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: '420px', overflowY: 'auto' }}>
            {runs.map(run => (
              <div
                key={run.id}
                onClick={() => setSelectedRunId(run.id)}
                style={runItemStyle(selectedRunId === run.id)}
              >
                <div style={{ fontWeight: 800, fontSize: '11px', display: 'flex', justifyContent: 'space-between' }}>
                  <span>#{run.id.slice(0, 8)}</span>
                  <span style={{ color: getStatusColor(run.status) }}>{run.status.toUpperCase()}</span>
                </div>
                <div style={{ fontSize: '9px', color: 'var(--muted)', marginTop: '2px', display: 'flex', justifyContent: 'space-between' }}>
                  <span>{run.dry_run ? 'DRY-RUN' : 'LIVE'}</span>
                  <span>{new Date(run.created_at).toLocaleTimeString('vi-VN')}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Evidence Viewer Panel */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {selectedRunId ? (
          <div style={panelStyle()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', borderBottom: '1px solid var(--border)', paddingBottom: '12px' }}>
              <div>
                <div style={{ fontSize: '10px', color: 'var(--muted)', textTransform: 'uppercase', fontWeight: 800 }}>
                  Hồ sơ chứng cứ & Audit Logs (Autopilot Evidence)
                </div>
                <div style={{ fontSize: '16px', fontWeight: 850, marginTop: '2px' }}>
                  Run ID: #{selectedRunId}
                </div>
              </div>

              <button
                type="button"
                disabled={actionPending || loadingEvidence}
                onClick={handleRefreshEvidence}
                style={buttonStyle()}
              >
                <RefreshCw size={12} className={actionPending ? 'animate-spin' : ''} /> THU THẬP BẰNG CHỨNG
              </button>
            </div>

            {loadingEvidence ? (
              <div style={{ color: 'var(--muted)', fontSize: '12px', padding: '24px', textAlign: 'center' }}>
                Đang tải dữ liệu chứng cứ...
              </div>
            ) : evidence ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '8px' }}>
                
                {/* Summary Row */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: '10px' }}>
                  <div style={statCardStyle('var(--accent)')}>
                    <div style={statValStyle()}>{evidence.summary.percent_complete}%</div>
                    <div style={statLblStyle()}>Tiến trình</div>
                  </div>
                  <div style={statCardStyle('var(--green)')}>
                    <div style={statValStyle()}>{evidence.summary.counts.posted}</div>
                    <div style={statLblStyle()}>Đăng thành công</div>
                  </div>
                  <div style={statCardStyle('var(--red)')}>
                    <div style={statValStyle()}>{evidence.summary.counts.failed}</div>
                    <div style={statLblStyle()}>Thất bại</div>
                  </div>
                  <div style={statCardStyle('var(--yellow)')}>
                    <div style={statValStyle()}>{evidence.summary.counts.queued}</div>
                    <div style={statLblStyle()}>Đang hàng chờ</div>
                  </div>
                </div>

                {/* Target Execution Details */}
                <div>
                  <div style={sectionTitleStyle()}>Chi tiết kết quả thực thi Target</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '6px' }}>
                    {evidence.summary.targets.map((target, idx) => {
                      const isSuccess = target.status === 'posted' || target.status === 'completed'
                      const isFailed = target.status === 'failed'
                      return (
                        <div key={target.id || idx} style={targetRowStyle(isSuccess, isFailed)}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <div>
                              <div style={{ fontWeight: 800, fontSize: '12px' }}>
                                Target: {target.target_registry_id?.slice(0, 8) || 'Unknown'}
                              </div>
                              <div style={{ fontSize: '10px', color: 'var(--muted)', marginTop: '2px' }}>
                                Channel: {target.channel_id || 'N/A'} · Lượt thử: {target.attempts}
                              </div>
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <span style={outcomeBadgeStyle(target.status)}>
                                {target.status.toUpperCase()}
                              </span>
                            </div>
                          </div>

                          {target.error_message && (
                            <div style={errorBoxStyle()}>
                              <AlertCircle size={12} style={{ color: 'var(--red)', flexShrink: 0, marginTop: '2px' }} />
                              <div style={{ fontSize: '10px', color: 'var(--red)' }}>
                                <strong>[{target.error_code || 'LỖI'}]</strong> {target.error_message}
                              </div>
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                </div>

                {/* Screenshots and Artifact refs */}
                <div>
                  <div style={sectionTitleStyle()}>Ảnh chụp bằng chứng & Tài liệu liên quan</div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '10px', marginTop: '6px' }}>
                    {evidence.artifact_refs && evidence.artifact_refs.length > 0 ? (
                      evidence.artifact_refs.map((artifact, idx) => {
                        const isImage = artifact.type === 'screenshot' || artifact.url?.endsWith('.png') || artifact.url?.endsWith('.jpg')
                        return (
                          <div key={idx} style={artifactCardStyle()}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', borderBottom: '1px solid var(--border)', paddingBottom: '6px', marginBottom: '6px' }}>
                              {isImage ? <Camera size={14} color="var(--accent)" /> : <FileText size={14} color="var(--muted)" />}
                              <span style={{ fontSize: '11px', fontWeight: 800, textTransform: 'uppercase' }}>
                                {artifact.type}
                              </span>
                            </div>

                            {isImage && artifact.url ? (
                              <div style={imgContainerStyle()}>
                                <img src={artifact.url} alt="Screenshot evidence" style={{ width: '100%', height: '100%', objectFit: 'contain', borderRadius: '4px' }} />
                              </div>
                            ) : (
                              <div style={{ fontSize: '10px', color: 'var(--muted)', wordBreak: 'break-all' }}>
                                Path: <code>{artifact.local_path || artifact.url}</code>
                              </div>
                            )}

                            {artifact.url && (
                              <a
                                href={artifact.url}
                                target="_blank"
                                rel="noreferrer"
                                style={linkStyle()}
                              >
                                Mở liên kết <ExternalLink size={10} />
                              </a>
                            )}
                          </div>
                        )
                      })
                    ) : (
                      <div style={{ fontSize: '11px', color: 'var(--muted)', gridColumn: '1 / -1', textAlign: 'center', padding: '12px', border: '1px dashed var(--border)', borderRadius: '8px' }}>
                        Chưa thu thập được ảnh chụp màn hình (screenshot) hoặc tệp log cho lượt chạy này.
                      </div>
                    )}
                  </div>
                </div>

              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px', padding: '40px', textAlign: 'center' }}>
                <AlertCircle size={36} color="var(--muted)" />
                <div style={{ fontSize: '13px', fontWeight: 800 }}>Chưa có tóm tắt chứng cứ</div>
                <div style={{ fontSize: '11px', color: 'var(--muted)', maxWidth: '300px' }}>
                  Lượt chạy autopilot này chưa hoàn thành hoặc chưa có tóm tắt chứng cứ được tạo. Nhấn nút "THU THẬP BẰNG CHỨNG" để quét.
                </div>
              </div>
            )}
          </div>
        ) : (
          <div style={emptyPanelStyle()}>
            <FileText size={48} color="var(--muted)" />
            <div style={{ fontSize: '14px', fontWeight: 700 }}>Chọn một lượt chạy để xem bằng chứng</div>
            <div style={{ fontSize: '12px', color: 'var(--muted)' }}>Danh sách các lượt chạy autopilot của dự án hiển thị ở danh mục bên trái.</div>
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
    fontSize: '11px',
    fontWeight: 850,
    color: 'var(--muted)',
    textTransform: 'uppercase',
    letterSpacing: '0.04em',
    borderBottom: '1px solid var(--border)',
    paddingBottom: '8px',
  }
}

function runItemStyle(active: boolean): React.CSSProperties {
  return {
    background: active ? 'rgba(37,99,235,0.06)' : 'var(--surface)',
    border: `1px solid ${active ? 'var(--accent)' : 'var(--border)'}`,
    borderRadius: '8px',
    padding: '8px 10px',
    cursor: 'pointer',
    display: 'flex',
    flexDirection: 'column',
    gap: '2px',
    transition: 'all 0.1s ease',
  }
}

function buttonStyle(): React.CSSProperties {
  return {
    border: '1px solid var(--border)',
    borderRadius: '8px',
    background: 'var(--surface)',
    color: 'var(--text)',
    padding: '6px 12px',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '6px',
    fontSize: '11px',
    fontWeight: 850,
    cursor: 'pointer',
    height: '30px',
  }
}

function statCardStyle(color: string): React.CSSProperties {
  return {
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderTop: `3px solid ${color}`,
    borderRadius: '8px',
    padding: '10px',
    textAlign: 'center',
  }
}

function statValStyle(): React.CSSProperties {
  return {
    fontSize: '18px',
    fontWeight: 850,
    color: 'var(--text)',
  }
}

function statLblStyle(): React.CSSProperties {
  return {
    fontSize: '9px',
    color: 'var(--muted)',
    fontWeight: 800,
    textTransform: 'uppercase',
    marginTop: '2px',
  }
}

function sectionTitleStyle(): React.CSSProperties {
  return {
    fontSize: '11px',
    fontWeight: 850,
    color: 'var(--muted)',
    textTransform: 'uppercase',
  }
}

function targetRowStyle(success: boolean, failed: boolean): React.CSSProperties {
  const borderLeft = success ? '3px solid var(--green)' : failed ? '3px solid var(--red)' : '3px solid var(--yellow)'
  return {
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderLeft,
    borderRadius: '8px',
    padding: '8px 12px',
  }
}

function outcomeBadgeStyle(status: string): React.CSSProperties {
  const isOk = status === 'posted' || status === 'completed' || status === 'success'
  const isErr = status === 'failed'
  const color = isOk ? 'var(--green)' : isErr ? 'var(--red)' : 'var(--yellow)'
  return {
    fontSize: '9px',
    fontWeight: 800,
    padding: '1px 5px',
    borderRadius: '4px',
    color,
    background: 'var(--card)',
    border: `1px solid ${color}`,
  }
}

function errorBoxStyle(): React.CSSProperties {
  return {
    display: 'flex',
    gap: '6px',
    background: 'rgba(220, 38, 38, 0.03)',
    border: '1px solid rgba(220, 38, 38, 0.1)',
    borderRadius: '6px',
    padding: '6px 8px',
    marginTop: '6px',
  }
}

function artifactCardStyle(): React.CSSProperties {
  return {
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: '8px',
    padding: '10px',
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'space-between',
  }
}

function imgContainerStyle(): React.CSSProperties {
  return {
    height: '120px',
    background: '#000',
    borderRadius: '4px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: '8px',
  }
}

function linkStyle(): React.CSSProperties {
  return {
    fontSize: '9px',
    color: 'var(--accent)',
    textDecoration: 'none',
    fontWeight: 800,
    display: 'inline-flex',
    alignItems: 'center',
    gap: '3px',
    marginTop: '6px',
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
