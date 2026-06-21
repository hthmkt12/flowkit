/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState, useEffect, useCallback } from 'react'
import { Check, X, Shield, AlertTriangle, RefreshCw, Clock } from 'lucide-react'
import { fetchAPI, postAPI } from '../../api/client'
import type { Project } from '../../types/projects'

interface ApprovalQueueTabProps {
  project: Project
  onMessage: (msg: string | null) => void
}

interface AgentTask {
  id: string
  account_id: string
  task_type: string
  status: string
  payload: string | Record<string, any> | null
  ref_id: string | null
  priority: number
  scheduled_at: string | null
  created_at: string
  updated_at: string
}

export default function ApprovalQueueTab({
  project,
  onMessage,
}: ApprovalQueueTabProps) {
  const [tasks, setTasks] = useState<AgentTask[]>([])
  const [loading, setLoading] = useState(true)
  const [actionPendingId, setActionPendingId] = useState<string | null>(null)

  const loadPendingTasks = useCallback(async () => {
    setLoading(true)
    try {
      // Fetch pending tasks from local agent
      const data = await fetchAPI<AgentTask[]>('/api/tasks?status=PENDING')
      
      // Filter by projectId inside task.payload
      const filtered = data.filter(task => {
        let payloadObj: any = {}
        if (typeof task.payload === 'string') {
          try {
            payloadObj = JSON.parse(task.payload)
          } catch {
            payloadObj = {}
          }
        } else if (task.payload && typeof task.payload === 'object') {
          payloadObj = task.payload
        }
        return payloadObj.projectId === project.id
      })
      
      setTasks(filtered)
    } catch {
      onMessage('Không tải được danh sách yêu cầu phê duyệt từ Agent.')
    } finally {
      setLoading(false)
    }
  }, [project.id, onMessage])

  useEffect(() => {
    loadPendingTasks()
    
    // Poll every 5 seconds for pending approvals
    const timer = setInterval(() => {
      loadPendingTasks()
    }, 5000)

    return () => clearInterval(timer)
  }, [loadPendingTasks])

  const handleApprove = async (taskId: string) => {
    setActionPendingId(taskId)
    try {
      await postAPI(`/api/tasks/${taskId}/approve`)
      onMessage('Đã PHÊ DUYỆT tác vụ live thành công.')
      setTasks(prev => prev.filter(t => t.id !== taskId))
    } catch (err: any) {
      const errorMsg = err?.response?.data?.detail || err?.message || 'Lỗi phê duyệt tác vụ.'
      onMessage(`Phê duyệt thất bại: ${errorMsg}`)
    } finally {
      setActionPendingId(null)
    }
  }

  const handleCancel = async (taskId: string) => {
    setActionPendingId(taskId)
    try {
      await postAPI(`/api/tasks/${taskId}/cancel`)
      onMessage('Đã HỦY/BỎ QUA tác vụ thành công.')
      setTasks(prev => prev.filter(t => t.id !== taskId))
    } catch (err: any) {
      const errorMsg = err?.response?.data?.detail || err?.message || 'Lỗi hủy tác vụ.'
      onMessage(`Hủy tác vụ thất bại: ${errorMsg}`)
    } finally {
      setActionPendingId(null)
    }
  }

  const getPayloadDetails = (task: AgentTask) => {
    let payloadObj: any = {}
    if (typeof task.payload === 'string') {
      try {
        payloadObj = JSON.parse(task.payload)
      } catch {
        payloadObj = {}
      }
    } else if (task.payload && typeof task.payload === 'object') {
      payloadObj = task.payload
    }
    return payloadObj
  }

  if (loading && tasks.length === 0) {
    return <div style={{ color: 'var(--muted)', fontSize: '12px', padding: '12px' }}>Đang tải danh sách chờ phê duyệt...</div>
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div style={panelStyle()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={panelTitleStyle()}>Hàng chờ phê duyệt (Approval Queue)</div>
            <div style={{ fontSize: '11px', color: 'var(--muted)', marginTop: '4px' }}>
              Các tác vụ Live R1-R4 cần sự phê duyệt thủ công của Operator để tiến hành dispatch.
            </div>
          </div>
          <button 
            type="button" 
            onClick={loadPendingTasks}
            style={iconBtnStyle()}
            title="Làm mới hàng chờ"
          >
            <RefreshCw size={12} />
          </button>
        </div>

        {tasks.length === 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px', padding: '32px', textAlign: 'center' }}>
            <Shield size={36} color="var(--green)" />
            <div style={{ fontSize: '13px', fontWeight: 800, color: 'var(--green)' }}>Hàng chờ sạch!</div>
            <div style={{ fontSize: '11px', color: 'var(--muted)' }}>
              Không có tác vụ nào đang chờ phê duyệt dưới dự án này.
            </div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {tasks.map(task => {
              const payload = getPayloadDetails(task)
              const safetyReason = payload.safetyReason || 'Yêu cầu kiểm tra ranh giới an toàn'
              
              return (
                <div key={task.id} style={taskCardStyle()}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'start', flexWrap: 'wrap' }}>
                    <div style={{ flex: 1, minWidth: '240px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontWeight: 850, fontSize: '13px', color: 'var(--accent)' }}>
                          {task.task_type}
                        </span>
                        <span style={priorityPillStyle()}>
                          Prio: {task.priority}
                        </span>
                        <span style={riskPillStyle()}>
                          R1 REQUIRES OPERATOR APPROVAL
                        </span>
                      </div>
                      
                      <div style={{ fontSize: '11px', marginTop: '6px', color: 'var(--text)' }}>
                        ID: <strong>{task.id}</strong> · Account ID: <strong>{task.account_id}</strong>
                      </div>

                      <div style={safetyReasonBoxStyle()}>
                        <AlertTriangle size={12} style={{ color: 'var(--yellow)', flexShrink: 0, marginTop: '2px' }} />
                        <div style={{ fontSize: '11px', fontStyle: 'italic', color: 'var(--yellow)', fontWeight: 600 }}>
                          {safetyReason}
                        </div>
                      </div>

                      {/* Display payload details */}
                      <div style={jsonDetailsStyle()}>
                        <div style={{ fontWeight: 700, marginBottom: '4px' }}>Dữ liệu Payload:</div>
                        <pre style={{ margin: 0, overflowX: 'auto', fontSize: '10px', color: 'var(--muted)' }}>
                          {JSON.stringify(payload, null, 2)}
                        </pre>
                      </div>

                      <div style={{ fontSize: '10px', color: 'var(--muted)', marginTop: '8px', display: 'flex', gap: '6px', alignItems: 'center' }}>
                        <Clock size={10} />
                        Tạo lúc: {new Date(task.created_at).toLocaleString('vi-VN')}
                      </div>
                    </div>

                    <div style={{ display: 'flex', gap: '8px' }}>
                      <button
                        type="button"
                        disabled={actionPendingId !== null}
                        onClick={() => handleApprove(task.id)}
                        style={approveBtnStyle()}
                      >
                        <Check size={14} /> DUYỆT LIVE
                      </button>

                      <button
                        type="button"
                        disabled={actionPendingId !== null}
                        onClick={() => handleCancel(task.id)}
                        style={cancelBtnStyle()}
                      >
                        <X size={14} /> BỎ QUA
                      </button>
                    </div>
                  </div>
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

function taskCardStyle(): React.CSSProperties {
  return {
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderLeft: '4px solid var(--yellow)',
    borderRadius: '10px',
    padding: '12px',
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
  }
}

function priorityPillStyle(): React.CSSProperties {
  return {
    padding: '1px 5px',
    borderRadius: '4px',
    background: 'var(--card)',
    border: '1px solid var(--border)',
    color: 'var(--text)',
    fontSize: '9px',
    fontWeight: 800,
  }
}

function riskPillStyle(): React.CSSProperties {
  return {
    padding: '1px 5px',
    borderRadius: '4px',
    background: 'rgba(217, 119, 6, 0.08)',
    border: '1px solid rgba(217, 119, 6, 0.25)',
    color: 'var(--yellow)',
    fontSize: '9px',
    fontWeight: 800,
  }
}

function safetyReasonBoxStyle(): React.CSSProperties {
  return {
    display: 'flex',
    gap: '6px',
    background: 'rgba(217, 119, 6, 0.04)',
    border: '1px solid rgba(217, 119, 6, 0.12)',
    borderRadius: '8px',
    padding: '8px',
    marginTop: '8px',
    alignItems: 'flex-start',
  }
}

function jsonDetailsStyle(): React.CSSProperties {
  return {
    background: 'var(--card)',
    border: '1px solid var(--border)',
    borderRadius: '8px',
    padding: '8px',
    marginTop: '8px',
    fontSize: '11px',
  }
}

function approveBtnStyle(): React.CSSProperties {
  return {
    border: 0,
    borderRadius: '8px',
    background: 'var(--green)',
    color: '#fff',
    padding: '6px 12px',
    display: 'inline-flex',
    alignItems: 'center',
    gap: '4px',
    fontSize: '11px',
    fontWeight: 850,
    cursor: 'pointer',
    height: '30px',
  }
}

function cancelBtnStyle(): React.CSSProperties {
  return {
    border: '1px solid var(--border)',
    borderRadius: '8px',
    background: 'var(--surface)',
    color: 'var(--red)',
    padding: '6px 12px',
    display: 'inline-flex',
    alignItems: 'center',
    gap: '4px',
    fontSize: '11px',
    fontWeight: 850,
    cursor: 'pointer',
    height: '30px',
  }
}
