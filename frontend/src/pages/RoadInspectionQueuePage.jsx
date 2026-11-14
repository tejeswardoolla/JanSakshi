import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  Wrench, MapPin, Clock, CheckCircle2, Eye, RefreshCw,
  AlertCircle, Upload, MessageSquare, ChevronRight, PlayCircle,
  FileCheck2, Shield, ExternalLink, Camera
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import AuthorityLayout from '../components/AuthorityLayout'
import { formatToIST, formatISTDateOnly } from '../utils/dateTime'

export default function RoadInspectionQueuePage() {
  const { authFetch, user } = useAuth()
  const [complaints, setComplaints] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [actionSuccess, setActionSuccess] = useState(null)
  const [actionLoading, setActionLoading] = useState(false)

  // Modals & Action States
  const [activeModal, setActiveModal] = useState(null) // 'notes', 'status', 'evidence'
  const [selectedComplaint, setSelectedComplaint] = useState(null)
  const [inspectionNotes, setInspectionNotes] = useState('')
  const [targetStatus, setTargetStatus] = useState('In Progress')
  const [statusNotes, setStatusNotes] = useState('')
  const [evidenceFile, setEvidenceFile] = useState(null)
  const [evidenceCaption, setEvidenceCaption] = useState('')

  const activeDeptId = localStorage.getItem('jansakshi_active_dept_id')
  const activeDeptCode = localStorage.getItem('jansakshi_active_dept_code') || 'RPW'
  const activeDeptName = localStorage.getItem('jansakshi_active_dept_name') || 'Roads & Public Works'

  useEffect(() => {
    fetchInspectionQueue()
  }, [])

  const fetchInspectionQueue = async () => {
    setLoading(true)
    setError(null)
    try {
      const url = activeDeptId
        ? `http://127.0.0.1:8000/api/authority/inspection-queue?department_id=${activeDeptId}`
        : 'http://127.0.0.1:8000/api/authority/inspection-queue'
      const res = await authFetch(url)
      if (!res.ok) throw new Error('Failed to load field inspection queue.')
      const data = await res.json()
      setComplaints(data.items || [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  // 1. Start Inspection Action
  const handleStartInspection = async (complaintId) => {
    setActionLoading(true)
    setActionSuccess(null)
    try {
      const res = await authFetch(`http://127.0.0.1:8000/api/authority/complaints/${complaintId}/status`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          status: 'Under Inspection',
          notes: `Physical field inspection initiated by ${user?.full_name || 'Department Officer'}.`
        })
      })
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}))
        throw new Error(errJson.detail || 'Failed to start inspection.')
      }
      setActionSuccess(`Physical inspection initiated for ${complaintId}. Work status advanced to Under Inspection.`)
      fetchInspectionQueue()
    } catch (err) {
      alert(err.message)
    } finally {
      setActionLoading(false)
    }
  }

  // 2. Add Inspection Notes
  const handleAddNotes = async (e) => {
    e.preventDefault()
    if (!inspectionNotes.trim() || !selectedComplaint) return
    setActionLoading(true)
    try {
      const res = await authFetch(`http://127.0.0.1:8000/api/authority/complaints/${selectedComplaint.complaint_id}/notes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          notes: `[Field Inspection Observation]: ${inspectionNotes.trim()}`
        })
      })
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}))
        throw new Error(errJson.detail || 'Failed to record notes.')
      }
      setActionSuccess(`Field inspection notes recorded for ${selectedComplaint.complaint_id}!`)
      setActiveModal(null)
      setInspectionNotes('')
      fetchInspectionQueue()
    } catch (err) {
      alert(err.message)
    } finally {
      setActionLoading(false)
    }
  }

  // 3. Update Work Progress
  const handleUpdateStatus = async (e) => {
    e.preventDefault()
    if (!selectedComplaint) return
    setActionLoading(true)
    try {
      const res = await authFetch(`http://127.0.0.1:8000/api/authority/complaints/${selectedComplaint.complaint_id}/status`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          status: targetStatus,
          notes: statusNotes.trim() ? `[Work Progress]: ${statusNotes.trim()}` : undefined
        })
      })
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}))
        throw new Error(errJson.detail || 'Failed to update work progress.')
      }
      setActionSuccess(`Work progress for ${selectedComplaint.complaint_id} updated to ${targetStatus}!`)
      setActiveModal(null)
      setStatusNotes('')
      fetchInspectionQueue()
    } catch (err) {
      alert(err.message)
    } finally {
      setActionLoading(false)
    }
  }

  // 4. Upload Inspection Evidence
  const handleUploadEvidence = async (e) => {
    e.preventDefault()
    if (!evidenceFile || !selectedComplaint) {
      alert('Please select an evidence file.')
      return
    }
    setActionLoading(true)
    try {
      const formData = new FormData()
      formData.append('file', evidenceFile)
      if (evidenceCaption) {
        formData.append('caption', evidenceCaption)
      }

      const res = await authFetch(`http://127.0.0.1:8000/api/authority/complaints/${selectedComplaint.complaint_id}/evidence`, {
        method: 'POST',
        body: formData
      })
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}))
        throw new Error(errJson.detail || 'Evidence upload failed.')
      }
      setActionSuccess(`Field inspection evidence uploaded for ${selectedComplaint.complaint_id}!`)
      setActiveModal(null)
      setEvidenceFile(null)
      setEvidenceCaption('')
      fetchInspectionQueue()
    } catch (err) {
      alert(err.message)
    } finally {
      setActionLoading(false)
    }
  }

  return (
    <AuthorityLayout
      pageTitle={activeDeptCode === 'RPW' ? 'Road Inspection Queue' : `${activeDeptName} Inspection Queue`}
      breadcrumbs={[activeDeptName, 'Inspection Queue']}
    >
      <div className="space-y-6 max-w-7xl mx-auto font-sans">
        {/* Banner */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-6 rounded-3xl bg-[#141722]/85 border border-white/[0.08] shadow-xs text-xs">
          <div className="flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-2xl bg-[#10131C] border border-white/[0.08] flex items-center justify-center flex-shrink-0">
              <Wrench className="w-5 h-5 text-[#F36B21]" />
            </div>
            <div>
              <p className="font-bold text-[#F5F5F5] text-base">
                {activeDeptCode === 'RPW' ? 'Road Inspection Queue' : `${activeDeptName} (${activeDeptCode}) Field Queue`}
              </p>
              <p className="text-[#A1A1AA] mt-0.5">
                Verified civic grievances assigned to {activeDeptName} requiring physical site inspection, engineering assessment, and field repair progress updates.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className="font-bold text-xs text-[#F5F5F5] bg-[#10131C] px-3.5 py-1.5 rounded-full border border-white/[0.08]">
              {complaints.length} Field Work Orders
            </span>
            <button
              onClick={fetchInspectionQueue}
              className="p-2 rounded-xl bg-[#10131C] hover:bg-white/[0.05] border border-white/[0.08] text-zinc-300 cursor-pointer transition-colors"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {actionSuccess && (
          <div className="p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              <span>{actionSuccess}</span>
            </div>
            <button onClick={() => setActionSuccess(null)} className="text-emerald-400 hover:underline cursor-pointer">Dismiss</button>
          </div>
        )}

        {/* Complaints Table Container */}
        <div className="bg-[#141722]/85 rounded-3xl border border-white/[0.08] overflow-hidden shadow-xs">
          {loading ? (
            <div className="py-24 text-center">
              <RefreshCw className="w-8 h-8 text-[#F36B21] animate-spin mx-auto mb-3" />
              <p className="text-xs text-[#A1A1AA] font-medium">Loading inspection queue...</p>
            </div>
          ) : complaints.length === 0 ? (
            <div className="py-24 text-center px-4">
              <FileCheck2 className="w-12 h-12 text-emerald-500 mx-auto mb-3" />
              <h3 className="text-base font-bold text-[#F5F5F5]">No road inspections are currently awaiting action.</h3>
              <p className="text-xs text-[#A1A1AA] mt-1 max-w-md mx-auto">
                All assigned work orders have either been inspected or progressed to completion.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="bg-[#10131C] border-b border-white/[0.08] text-[#A1A1AA] font-bold uppercase text-[10px] tracking-wider">
                    <th className="py-4 px-5">Work Order ID</th>
                    <th className="py-4 px-4">Hazard Category</th>
                    <th className="py-4 px-4">Location Coordinates</th>
                    <th className="py-4 px-4">Work Status</th>
                    <th className="py-4 px-4">Evidence</th>
                    <th className="py-4 px-5 text-center">Field Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/[0.08]">
                  {complaints.map((c) => (
                    <tr key={c.complaint_id} className="hover:bg-[#10131C]/60 transition-colors group">
                      <td className="py-4 px-5 whitespace-nowrap">
                        <Link
                          to={`/authority/work-orders/${c.complaint_id}?dept=${activeDeptId}`}
                          className="font-bold text-[#F5F5F5] hover:text-[#F36B21] transition-colors flex items-center gap-1.5"
                        >
                          <span>{c.complaint_id}</span>
                          <ExternalLink className="w-3 h-3 text-zinc-500 group-hover:text-[#F36B21]" />
                        </Link>
                        <span className="text-[10px] text-zinc-500 block mt-0.5">
                          Assigned: {c.assigned_at ? formatToIST(c.assigned_at) : 'Active'}
                        </span>
                      </td>

                      <td className="py-4 px-4">
                        <span className="font-semibold text-[#F5F5F5] block">{c.category}</span>
                        <p className="text-[#A1A1AA] text-[11px] line-clamp-1 mt-0.5 max-w-xs">{c.description}</p>
                      </td>

                      <td className="py-4 px-4">
                        {c.latitude && c.longitude ? (
                          <div>
                            <div className="flex items-center gap-1.5 font-medium text-[#F5F5F5]">
                              <MapPin className="w-3.5 h-3.5 text-zinc-500" />
                              <span>{c.latitude.toFixed(5)}, {c.longitude.toFixed(5)}</span>
                            </div>
                            {c.google_maps_url && (
                              <a
                                href={c.google_maps_url}
                                target="_blank"
                                rel="noreferrer"
                                className="inline-flex items-center gap-1 text-[10px] text-[#F36B21] hover:underline mt-0.5"
                              >
                                <span>Google Maps</span>
                                <ExternalLink className="w-2.5 h-2.5" />
                              </a>
                            )}
                          </div>
                        ) : (
                          <span className="text-zinc-500 italic">Coordinates Pending</span>
                        )}
                      </td>

                      <td className="py-4 px-4 whitespace-nowrap">
                        <span className="px-2.5 py-1 rounded-full text-[10px] font-bold bg-white/[0.05] text-[#F5F5F5] border border-stone-200">
                          {c.admin_status || 'Assigned'}
                        </span>
                      </td>

                      <td className="py-4 px-4 whitespace-nowrap text-[#A1A1AA] font-medium">
                        {c.evidence_count} file(s)
                      </td>

                      <td className="py-4 px-5 text-center whitespace-nowrap">
                        <div className="flex items-center justify-center gap-2">
                          {c.admin_status === 'Assigned' && (
                            <button
                              onClick={() => handleStartInspection(c.complaint_id)}
                              disabled={actionLoading}
                              className="px-3 py-1.5 rounded-xl bg-[#F36B21] hover:bg-[#E05A10] text-white text-xs font-semibold flex items-center gap-1.5 shadow-xs cursor-pointer transition-colors"
                            >
                              <PlayCircle className="w-3.5 h-3.5 text-emerald-400" />
                              <span>Start Inspection</span>
                            </button>
                          )}

                          <button
                            onClick={() => {
                              setSelectedComplaint(c)
                              setInspectionNotes('')
                              setActiveModal('notes')
                            }}
                            className="px-3 py-1.5 rounded-xl bg-[#141722]/85 hover:bg-white/[0.03] border border-white/[0.08] text-zinc-300 text-xs font-semibold flex items-center gap-1.5 shadow-xs cursor-pointer"
                          >
                            <MessageSquare className="w-3.5 h-3.5 text-zinc-500" />
                            <span>Notes</span>
                          </button>

                          <button
                            onClick={() => {
                              setSelectedComplaint(c)
                              setTargetStatus(c.admin_status || 'In Progress')
                              setStatusNotes('')
                              setActiveModal('status')
                            }}
                            className="px-3 py-1.5 rounded-xl bg-[#141722]/85 hover:bg-white/[0.03] border border-white/[0.08] text-zinc-300 text-xs font-semibold flex items-center gap-1.5 shadow-xs cursor-pointer"
                          >
                            <Clock className="w-3.5 h-3.5 text-[#F36B21]" />
                            <span>Progress</span>
                          </button>

                          <button
                            onClick={() => {
                              setSelectedComplaint(c)
                              setEvidenceFile(null)
                              setEvidenceCaption('')
                              setActiveModal('evidence')
                            }}
                            className="px-3 py-1.5 rounded-xl bg-[#141722]/85 hover:bg-white/[0.03] border border-white/[0.08] text-zinc-300 text-xs font-semibold flex items-center gap-1.5 shadow-xs cursor-pointer"
                          >
                            <Camera className="w-3.5 h-3.5 text-sky-600" />
                            <span>Upload Evidence</span>
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Modal: Add Notes */}
        {activeModal === 'notes' && (
          <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div className="bg-[#141722]/85 rounded-3xl p-6 max-w-md w-full border border-white/[0.08] shadow-2xl space-y-4">
              <h3 className="text-base font-bold text-[#F5F5F5]">Add Inspection Notes</h3>
              <p className="text-xs text-[#A1A1AA]">Record field observations for {selectedComplaint?.complaint_id}.</p>
              <textarea
                required
                rows={3}
                value={inspectionNotes}
                onChange={(e) => setInspectionNotes(e.target.value)}
                placeholder="e.g. Visual inspection confirmed severe asphalt deterioration..."
                className="w-full p-3 rounded-xl bg-[#10131C] border border-white/[0.08] text-xs text-[#F5F5F5]"
              />
              <div className="flex justify-end gap-2 pt-2">
                <button onClick={() => setActiveModal(null)} className="px-4 py-2 text-xs font-semibold text-[#A1A1AA]">Cancel</button>
                <button onClick={handleAddNotes} disabled={actionLoading} className="px-4 py-2 rounded-xl bg-[#F36B21] text-white text-xs font-semibold">
                  Save Notes
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Modal: Update Status */}
        {activeModal === 'status' && (
          <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div className="bg-[#141722]/85 rounded-3xl p-6 max-w-md w-full border border-white/[0.08] shadow-2xl space-y-4">
              <h3 className="text-base font-bold text-[#F5F5F5]">Update Work Status</h3>
              <p className="text-xs text-[#A1A1AA]">Update progress for {selectedComplaint?.complaint_id}.</p>
              <div>
                <label className="block text-xs font-semibold text-zinc-300 mb-1">Status</label>
                <select
                  value={targetStatus}
                  onChange={(e) => setTargetStatus(e.target.value)}
                  className="w-full p-2.5 rounded-xl bg-[#10131C] border border-white/[0.08] text-xs text-[#F5F5F5] font-semibold"
                >
                  <option value="Under Inspection">Under Inspection (Field crew on site)</option>
                  <option value="In Progress">In Progress (Active repairs underway)</option>
                  <option value="Resolution Submitted">Resolution Submitted (Repairs completed, submit for closure)</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-zinc-300 mb-1">Status Notes</label>
                <textarea
                  rows={2}
                  value={statusNotes}
                  onChange={(e) => setStatusNotes(e.target.value)}
                  placeholder="e.g. Asphalt base poured, awaiting final compaction roller..."
                  className="w-full p-3 rounded-xl bg-[#10131C] border border-white/[0.08] text-xs text-[#F5F5F5]"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button onClick={() => setActiveModal(null)} className="px-4 py-2 text-xs font-semibold text-[#A1A1AA]">Cancel</button>
                <button onClick={handleUpdateStatus} disabled={actionLoading} className="px-4 py-2 rounded-xl bg-[#F36B21] text-white text-xs font-semibold">
                  Update Status
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Modal: Upload Evidence */}
        {activeModal === 'evidence' && (
          <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div className="bg-[#141722]/85 rounded-3xl p-6 max-w-md w-full border border-white/[0.08] shadow-2xl space-y-4">
              <h3 className="text-base font-bold text-[#F5F5F5]">Upload Inspection Evidence</h3>
              <p className="text-xs text-[#A1A1AA]">Upload site photograph or repair verification file for {selectedComplaint?.complaint_id}.</p>
              <form onSubmit={handleUploadEvidence} className="space-y-4">
                <input
                  type="file"
                  required
                  accept="image/*,video/*"
                  onChange={(e) => setEvidenceFile(e.target.files[0])}
                  className="w-full p-2 rounded-xl border border-white/[0.08] text-xs bg-[#10131C]"
                />
                <input
                  type="text"
                  value={evidenceCaption}
                  onChange={(e) => setEvidenceCaption(e.target.value)}
                  placeholder="Caption (e.g. Post-patching surface inspection photograph)"
                  className="w-full p-2.5 rounded-xl bg-[#10131C] border border-white/[0.08] text-xs text-[#F5F5F5]"
                />
                <div className="flex justify-end gap-2 pt-2">
                  <button type="button" onClick={() => setActiveModal(null)} className="px-4 py-2 text-xs font-semibold text-[#A1A1AA]">Cancel</button>
                  <button type="submit" disabled={actionLoading} className="px-4 py-2 rounded-xl bg-[#F36B21] text-white text-xs font-semibold">
                    Upload File
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </AuthorityLayout>
  )
}
