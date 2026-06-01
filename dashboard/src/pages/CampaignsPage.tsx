import { useState, useEffect, useCallback } from 'react'
import { Plus, Play, Eye, FileText, CheckSquare, Layers, AlertCircle } from 'lucide-react'
import { fetchAPI, postAPI, deleteAPI } from '../api/client'
import PolicyPreviewPanel from '../components/projects/PolicyPreviewPanel'
import type { Project, AffiliateCampaign, PolicyPreviewResult, CampaignDryRunResponse, TargetRegistry } from '../types/projects'
import type { ContentItem } from '../types'

export default function CampaignsPage() {
  const [projects, setProjects] = useState<Project[]>([])
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null)
  
  const [campaigns, setCampaigns] = useState<AffiliateCampaign[]>([])
  const [selectedCampaignId, setSelectedCampaignId] = useState<string | null>(null)

  const [contentItems, setContentItems] = useState<ContentItem[]>([])
  const [targets, setTargets] = useState<TargetRegistry[]>([])

  const [actionPending, setActionPending] = useState(false)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  // Policy preview and dry-run outputs
  const [previewResult, setPreviewResult] = useState<PolicyPreviewResult | null>(null)
  const [dryRunResult, setDryRunResult] = useState<CampaignDryRunResponse | null>(null)

  // Creation forms
  const [newCampaignName, setNewCampaignName] = useState('')
  const [newCampaignOffer, setNewCampaignOffer] = useState('')
  const [newCampaignNetwork, setNewCampaignNetwork] = useState('')
  
  // Association forms
  const [attachContentId, setAttachContentId] = useState('')
  const [attachContentOrder, setAttachContentOrder] = useState(1)
  const [attachTargetId, setAttachTargetId] = useState('')
  const [attachTargetOrder, setAttachTargetOrder] = useState(1)

  const loadProjects = useCallback(async () => {
    try {
      const data = await fetchAPI<Project[]>('/api/projects')
      setProjects(data)
      if (data.length > 0 && !selectedProjectId) {
        setSelectedProjectId(data[0].id)
      }
    } catch {
      setMessage('Không tải được danh sách dự án.')
    }
  }, [selectedProjectId])

  const loadCampaigns = useCallback(async (projectId: string) => {
    try {
      const data = await fetchAPI<AffiliateCampaign[]>(`/api/projects/${projectId}/campaigns`)
      setCampaigns(data)
      if (data.length > 0 && !selectedCampaignId) {
        setSelectedCampaignId(data[0].id)
      }
    } catch {
      setMessage('Không tải được danh sách chiến dịch.')
    }
  }, [selectedCampaignId])

  const loadContentLibrary = useCallback(async () => {
    try {
      const data = await fetchAPI<ContentItem[]>('/api/content-items')
      setContentItems(data)
    } catch {
      setMessage('Không tải được thư viện nội dung.')
    }
  }, [])

  const loadTargetRegistry = useCallback(async (projectId: string) => {
    try {
      const data = await fetchAPI<TargetRegistry[]>(`/api/projects/${projectId}/targets`)
      setTargets(data.filter(t => t.status === 'active'))
    } catch {
      setMessage('Không tải được danh sách targets.')
    }
  }, [])

  useEffect(() => {
    loadProjects()
    loadContentLibrary()
  }, [loadProjects, loadContentLibrary])

  useEffect(() => {
    if (selectedProjectId) {
      loadCampaigns(selectedProjectId)
      loadTargetRegistry(selectedProjectId)
    } else {
      setCampaigns([])
      setTargets([])
    }
  }, [selectedProjectId, loadCampaigns, loadTargetRegistry])

  const handleCreateCampaign = async () => {
    const name = newCampaignName.trim()
    if (!selectedProjectId) return
    if (!name) {
      setMessage('Nhập tên chiến dịch.')
      return
    }
    setActionPending(true)
    try {
      const created = await postAPI<AffiliateCampaign>(`/api/projects/${selectedProjectId}/campaigns`, {
        name,
        offer_name: newCampaignOffer.trim() || null,
        affiliate_network: newCampaignNetwork.trim() || null,
        status: 'draft',
      })
      setCampaigns(prev => [created, ...prev])
      setSelectedCampaignId(created.id)
      setNewCampaignName('')
      setNewCampaignOffer('')
      setNewCampaignNetwork('')
      setMessage(`Đã tạo chiến dịch: ${created.name}`)
    } catch {
      setMessage('Không tạo được chiến dịch mới.')
    } finally {
      setActionPending(false)
    }
  }

  const selectedCampaign = campaigns.find(c => c.id === selectedCampaignId) || null

  const handleAttachContent = async () => {
    if (!selectedProjectId || !selectedCampaignId || !attachContentId) return
    setActionPending(true)
    try {
      const updated = await postAPI<AffiliateCampaign>(`/api/projects/${selectedProjectId}/campaigns/${selectedCampaignId}/content`, {
        content_item_id: attachContentId,
        sort_order: attachContentOrder,
        options: {},
      })
      setCampaigns(prev => prev.map(c => c.id === selectedCampaignId ? updated : c))
      setAttachContentId('')
      setAttachContentOrder(prev => prev + 1)
      setPreviewResult(null)
      setMessage('Đã liên kết nội dung vào chiến dịch.')
    } catch {
      setMessage('Không liên kết được nội dung.')
    } finally {
      setActionPending(false)
    }
  }

  const handleDetachContent = async (contentItemId: string) => {
    if (!selectedProjectId || !selectedCampaignId) return
    setActionPending(true)
    try {
      const updated = await deleteAPI<AffiliateCampaign>(`/api/projects/${selectedProjectId}/campaigns/${selectedCampaignId}/content/${contentItemId}`)
      setCampaigns(prev => prev.map(c => c.id === selectedCampaignId ? updated : c))
      setPreviewResult(null)
      setMessage('Đã hủy liên kết nội dung.')
    } catch {
      setMessage('Không hủy liên kết nội dung được.')
    } finally {
      setActionPending(false)
    }
  }

  const handleAttachTarget = async () => {
    if (!selectedProjectId || !selectedCampaignId || !attachTargetId) return
    setActionPending(true)
    try {
      await postAPI<AffiliateCampaign['content_items']>(`/api/projects/${selectedProjectId}/campaigns/${selectedCampaignId}/targets`, {
        target_registry_id: attachTargetId,
        sort_order: attachTargetOrder,
        options: {},
      })
      // Reload campaign target set
      if (selectedCampaign) {
        const fullCampaign = await fetchAPI<AffiliateCampaign>(`/api/projects/${selectedProjectId}/campaigns/${selectedCampaignId}`)
        setCampaigns(prev => prev.map(c => c.id === selectedCampaignId ? fullCampaign : c))
      }
      setAttachTargetId('')
      setAttachTargetOrder(prev => prev + 1)
      setPreviewResult(null)
      setMessage('Đã liên kết Target vào chiến dịch.')
    } catch {
      setMessage('Không liên kết được Target.')
    } finally {
      setActionPending(false)
    }
  }

  const handleDetachTarget = async (targetRegistryId: string) => {
    if (!selectedProjectId || !selectedCampaignId) return
    setActionPending(true)
    try {
      await deleteAPI(`/api/projects/${selectedProjectId}/campaigns/${selectedCampaignId}/targets/${targetRegistryId}`)
      if (selectedCampaign) {
        const fullCampaign = await fetchAPI<AffiliateCampaign>(`/api/projects/${selectedProjectId}/campaigns/${selectedCampaignId}`)
        setCampaigns(prev => prev.map(c => c.id === selectedCampaignId ? fullCampaign : c))
      }
      setPreviewResult(null)
      setMessage('Đã hủy liên kết Target.')
    } catch {
      setMessage('Không hủy liên kết Target được.')
    } finally {
      setActionPending(false)
    }
  }

  const handlePolicyPreview = async () => {
    if (!selectedProjectId || !selectedCampaignId) return
    setPreviewLoading(true)
    setPreviewResult(null)
    setDryRunResult(null)
    try {
      const result = await postAPI<PolicyPreviewResult>(`/api/projects/${selectedProjectId}/campaigns/${selectedCampaignId}/runs/policy-preview`, {
        start_at: new Date().toISOString(),
        spacing_minutes: 30,
        input_summary: { source: 'FBKit UI dashboard' },
      })
      setPreviewResult(result)
      setMessage('Mô phỏng chính sách (policy preview) hoàn tất.')
    } catch (err: any) {
      const errorMsg = err?.response?.data?.detail || 'Lỗi chạy mô phỏng chính sách.'
      setMessage(`Không chạy được mô phỏng: ${errorMsg}`)
    } finally {
      setPreviewLoading(false)
    }
  }

  const handleLaunchDryRun = async () => {
    if (!selectedProjectId || !selectedCampaignId) return
    setActionPending(true)
    setPreviewResult(null)
    setDryRunResult(null)
    try {
      const result = await postAPI<CampaignDryRunResponse>(`/api/projects/${selectedProjectId}/campaigns/${selectedCampaignId}/runs/dry-run`, {
        start_at: new Date().toISOString(),
        spacing_minutes: 30,
        delay_policy: { min_delay_seconds: 60, max_delay_seconds: 120 },
      })
      setDryRunResult(result)
      setMessage(`BẮT ĐẦU WAVE DRY-RUN: Đã xếp hàng ${result.job_count} jobs cho ${result.planned_action_count} dispatches.`)
    } catch (err: any) {
      const errorMsg = err?.response?.data?.detail || 'Lỗi chạy dry-run.'
      setMessage(`Không tạo được wave: ${errorMsg}`)
    } finally {
      setActionPending(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap' }}>
        <div>
          <div style={{ fontSize: '22px', fontWeight: 850 }}>Campaign Planner</div>
          <div style={{ fontSize: '12px', color: 'var(--muted)' }}>Lên kế hoạch đăng bài, chọn danh sách nội dung và target, chạy dry-run wave.</div>
        </div>

        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <label style={{ fontSize: '11px', color: 'var(--muted)', fontWeight: 800 }}>DỰ ÁN:</label>
          <select 
            aria-label="Chọn dự án"
            value={selectedProjectId || ''} 
            onChange={e => setSelectedProjectId(e.target.value || null)} 
            style={{ ...inputStyle(), width: '180px', padding: '6px 10px' }}
          >
            {projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </div>
      </div>

      {message && <div style={messageStyle()}>{message}</div>}

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(280px, 1fr) minmax(360px, 2.2fr)', gap: '16px', alignItems: 'start' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <section style={panelStyle()}>
            <div style={{ fontSize: '13px', fontWeight: 850, marginBottom: '10px' }}>Chiến dịch dự án</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {campaigns.map(c => (
                <div 
                  key={c.id} 
                  onClick={() => { setSelectedCampaignId(c.id); setPreviewResult(null); setDryRunResult(null); }}
                  style={campaignItemStyle(selectedCampaignId === c.id)}
                >
                  <div style={{ fontWeight: 800 }}>{c.name}</div>
                  <div style={{ fontSize: '10px', color: 'var(--muted)', marginTop: '2px' }}>
                    Offer: {c.offer_name || 'N/A'} · Network: {c.affiliate_network || 'N/A'}
                  </div>
                  <div style={{ marginTop: '4px' }}>
                    <span style={statusBadgeStyle(c.status)}>{c.status.toUpperCase()}</span>
                  </div>
                </div>
              ))}
              {campaigns.length === 0 && <div style={{ fontSize: '12px', color: 'var(--muted)', textAlign: 'center', padding: '12px' }}>Chưa có chiến dịch nào.</div>}
            </div>
          </section>

          <section style={panelStyle()}>
            <div style={{ fontSize: '13px', fontWeight: 850, marginBottom: '10px' }}>+ Tạo chiến dịch mới</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <input value={newCampaignName} onChange={e => setNewCampaignName(e.target.value)} placeholder="Tên chiến dịch (ví dụ: Serum Launch)" style={inputStyle()} />
              <input value={newCampaignOffer} onChange={e => setNewCampaignOffer(e.target.value)} placeholder="Tên Affiliate Offer" style={inputStyle()} />
              <input value={newCampaignNetwork} onChange={e => setNewCampaignNetwork(e.target.value)} placeholder="Affiliate Network" style={inputStyle()} />
              
              <button 
                type="button" 
                onClick={handleCreateCampaign} 
                disabled={actionPending || !selectedProjectId}
                style={buttonStyle('#2563eb')}
              >
                <Plus size={14} /> TẠO CHIẾN DỊCH
              </button>
            </div>
          </section>
        </div>

        {selectedCampaign ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
              <section style={panelStyle()}>
                <div style={{ fontSize: '13px', fontWeight: 850 }}><FileText size={14} style={{ display: 'inline', marginRight: '4px' }} /> Nội dung chiến dịch</div>
                
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: '180px', overflowY: 'auto' }}>
                  {selectedCampaign.content_items?.map(item => (
                    <div key={item.content_item_id} style={associationStyle()}>
                      <div>
                        <div style={{ fontWeight: 800 }}>{item.title || 'Nội dung không tiêu đề'}</div>
                        <div style={{ fontSize: '9px', color: 'var(--muted)' }}>Type: {item.content_type} · Order: {item.sort_order}</div>
                      </div>
                      <button type="button" onClick={() => handleDetachContent(item.content_item_id)} style={detachBtnStyle()}>GỠ</button>
                    </div>
                  ))}
                  {(!selectedCampaign.content_items || selectedCampaign.content_items.length === 0) && <div style={{ fontSize: '11px', color: 'var(--muted)', textAlign: 'center', padding: '10px' }}>Chưa có nội dung liên kết.</div>}
                </div>

                <div style={{ borderTop: '1px solid var(--border)', paddingTop: '10px', display: 'flex', gap: '6px' }}>
                  <select 
                    aria-label="Chọn nội dung để liên kết"
                    value={attachContentId} 
                    onChange={e => setAttachContentId(e.target.value)} 
                    style={inputStyle()}
                  >
                    <option value="">-- Liên kết nội dung --</option>
                    {contentItems.map(item => (
                      <option key={item.id} value={item.id}>{item.title || item.body.slice(0, 30)}</option>
                    ))}
                  </select>
                  <input type="number" value={attachContentOrder} onChange={e => setAttachContentOrder(Number(e.target.value))} style={{ ...inputStyle(), width: '60px' }} />
                  <button type="button" onClick={handleAttachContent} disabled={actionPending} style={buttonStyle('#16a34a')}>THÊM</button>
                </div>
              </section>

              <section style={panelStyle()}>
                <div style={{ fontSize: '13px', fontWeight: 850 }}><CheckSquare size={14} style={{ display: 'inline', marginRight: '4px' }} /> Targets chiến dịch</div>
                
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: '180px', overflowY: 'auto' }}>
                  {/* Note: since AffiliateCampaign does not aggregate targets natively in campaign list, we rely on details load, or we fetch targets separately */}
                  {targets.filter(t => t.rules?.campaign_id === selectedCampaign.id).map(target => (
                    <div key={target.id} style={associationStyle()}>
                      <div>
                        <div style={{ fontWeight: 800 }}>{target.label}</div>
                        <div style={{ fontSize: '9px', color: 'var(--muted)' }}>Type: {target.target_type} · Readiness: {target.readiness}</div>
                      </div>
                      <button type="button" onClick={() => handleDetachTarget(target.id)} style={detachBtnStyle()}>GỠ</button>
                    </div>
                  ))}
                  {targets.filter(t => t.rules?.campaign_id === selectedCampaign.id).length === 0 && <div style={{ fontSize: '11px', color: 'var(--muted)', textAlign: 'center', padding: '10px' }}>Chưa có target liên kết.</div>}
                </div>

                <div style={{ borderTop: '1px solid var(--border)', paddingTop: '10px', display: 'flex', gap: '6px' }}>
                  <select 
                    aria-label="Chọn target để liên kết"
                    value={attachTargetId} 
                    onChange={e => setAttachTargetId(e.target.value)} 
                    style={inputStyle()}
                  >
                    <option value="">-- Liên kết Target --</option>
                    {targets.filter(t => t.rules?.campaign_id !== selectedCampaign.id).map(target => (
                      <option key={target.id} value={target.id}>{target.label}</option>
                    ))}
                  </select>
                  <input type="number" value={attachTargetOrder} onChange={e => setAttachTargetOrder(Number(e.target.value))} style={{ ...inputStyle(), width: '60px' }} />
                  <button type="button" onClick={handleAttachTarget} disabled={actionPending} style={buttonStyle('#16a34a')}>THÊM</button>
                </div>
              </section>
            </div>

            <section style={panelStyle()}>
              <div style={{ fontSize: '13px', fontWeight: 850 }}><Layers size={14} style={{ display: 'inline', marginRight: '4px' }} /> Vận hành chính sách & Dry-run</div>
              
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                <button 
                  type="button" 
                  onClick={handlePolicyPreview} 
                  disabled={previewLoading || actionPending}
                  style={buttonStyle('#2563eb')}
                >
                  <Eye size={14} /> CHẠY MÔ PHỎNG CHÍNH SÁCH
                </button>
                
                <button 
                  type="button" 
                  onClick={handleLaunchDryRun} 
                  disabled={previewLoading || actionPending}
                  style={buttonStyle('#16a34a')}
                >
                  <Play size={14} /> KHỞI CHẠY DRY-RUN WAVE
                </button>
              </div>

              <PolicyPreviewPanel preview={previewResult} loading={previewLoading} />

              {dryRunResult && (
                <div style={dryRunResultStyle()}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 850, fontSize: '12px' }}>
                    <CheckSquare size={14} /> Wave Dry-run đã được kích hoạt thành công!
                  </div>
                  <div style={{ fontSize: '11px', marginTop: '4px', color: 'var(--muted)' }}>
                    Tổng số job được tạo: {dryRunResult.job_count} · Tổng dispatches: {dryRunResult.planned_action_count}
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginTop: '6px' }}>
                    {dryRunResult.jobs.map(job => (
                      <div key={job.id} style={{ fontSize: '11px', borderBottom: '1px solid rgba(0,0,0,0.04)', paddingBottom: '3px' }}>
                        Job ID: <strong>{job.id.slice(0, 8)}</strong> · Status: <strong>{job.status}</strong> · Targets: {job.targets.length}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </section>
          </div>
        ) : (
          <div style={emptyPanelStyle()}>
            <AlertCircle size={48} color="var(--muted)" />
            <div style={{ fontSize: '14px', fontWeight: 700 }}>Chọn một chiến dịch để lên kế hoạch</div>
            <div style={{ fontSize: '12px', color: 'var(--muted)' }}>Tạo chiến dịch mới hoặc chọn từ danh sách bên trái.</div>
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

function campaignItemStyle(active: boolean): React.CSSProperties {
  return {
    background: active ? 'rgba(59,130,246,0.06)' : 'var(--surface)',
    border: `1px solid ${active ? 'var(--accent)' : 'var(--border)'}`,
    borderRadius: '12px',
    padding: '12px',
    cursor: 'pointer',
    display: 'flex',
    flexDirection: 'column',
    gap: '3px',
    transition: 'all 0.1s ease',
  }
}

function statusBadgeStyle(status: string): React.CSSProperties {
  const color = status === 'ready' ? 'var(--green)' : status === 'paused' ? 'var(--yellow)' : 'var(--muted)'
  return {
    fontSize: '9px',
    fontWeight: 800,
    color,
    background: 'var(--card)',
    border: `1px solid ${color}`,
    borderRadius: '4px',
    padding: '1px 4px',
  }
}

function associationStyle(): React.CSSProperties {
  return {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: '8px',
    padding: '6px 10px',
    fontSize: '11px',
  }
}

function detachBtnStyle(): React.CSSProperties {
  return {
    border: 0,
    background: 'transparent',
    color: 'var(--red)',
    fontWeight: 800,
    cursor: 'pointer',
    padding: '4px',
  }
}

function dryRunResultStyle(): React.CSSProperties {
  return {
    background: 'rgba(34,197,94,0.05)',
    border: '1px solid rgba(34,197,94,0.2)',
    borderRadius: '12px',
    padding: '12px',
    fontSize: '12px',
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
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
