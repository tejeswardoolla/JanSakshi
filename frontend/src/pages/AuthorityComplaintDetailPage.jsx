import React, { useState, useEffect } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import {
  ArrowLeft, Shield, MapPin, Clock, CheckCircle2, XCircle,
  AlertTriangle, Flame, Building2, User, Send, ExternalLink,
  Cpu, FileText, CheckCircle, RefreshCw, AlertCircle, Eye,
  Lock, MessageSquare, HelpCircle, Layers, Wrench
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { getApiUrl } from '../config/api'
import AuthorityLayout from '../components/AuthorityLayout'
import DepartmentWorkOrderDetailPage from './authority/DepartmentWorkOrderDetailPage'
import { formatToIST, formatISTDateOnly, formatISTTimeOnly } from '../utils/dateTime'

export default function AuthorityComplaintDetailPage() {
  const { id } = useParams()
  const { user, isAuthenticated, authFetch, token } = useAuth()
  const navigate = useNavigate()

  // Route role-awareness: Department Officers always receive the dedicated Work Order inspection experience
  if (user?.role === 'department_officer') {
    return <DepartmentWorkOrderDetailPage />
  }

  const [complaint, setComplaint] = useState(null)
  const [departments, setDepartments] = useState([])
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(false)
  const [error, setError] = useState(null)
  const [actionSuccess, setActionSuccess] = useState(null)

  // Modals & Action States
  const [activeModal, setActiveModal] = useState(null) // 'verify', 'reject', 'request_info', 'assign', 'status', 'escalate', 'note', 'evidence_view'
  const [verifyNotes, setVerifyNotes] = useState('')
  const [rejectReason, setRejectReason] = useState('')
  const [infoNotes, setInfoNotes] = useState('')
  const [selectedDeptId, setSelectedDeptId] = useState('')
  const [selectedOfficerId, setSelectedOfficerId] = useState('')
  const [assignNotes, setAssignNotes] = useState('')
  const [targetStatus, setTargetStatus] = useState('')
  const [statusNotes, setStatusNotes] = useState('')
  const [escalationLevel, setEscalationLevel] = useState(1)
  const [escalationReason, setEscalationReason] = useState('')
  const [escalatedTo, setEscalatedTo] = useState('Municipal Commissioner')
  const [newInternalNote, setNewInternalNote] = useState('')
  const [selectedEvidenceView, setSelectedEvidenceView] = useState(null)

  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/authority/login')
      return
    }
    fetchDetail()
    fetchDepartments()
  }, [id, isAuthenticated, navigate])

  const fetchDetail = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await authFetch(`/api/authority/complaints/${id}`)
      if (!res.ok) {
        throw new Error(`Failed to load complaint ${id}.`)
      }
      const data = await res.json()
      setComplaint(data)
      if (data.department) {
        setSelectedDeptId(data.department.id.toString())
      }
      setTargetStatus(data.admin_status || 'Received')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const fetchDepartments = async () => {
    try {
      const res = await authFetch('/api/authority/departments')
      if (res.ok) {
        const json = await res.json()
        setDepartments(json.departments || [])
      }
    } catch {
      // Non-blocking
    }
  }

  // --- Action Handlers ---
  const handleVerify = async () => {
    setActionLoading(true)
    setActionSuccess(null)
    try {
      const res = await authFetch(`/api/authority/complaints/${id}/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ notes: verifyNotes })
      })
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}))
        throw new Error(errJson.detail || 'Verification action failed.')
      }
      setActionSuccess('Complaint successfully verified!')
      setActiveModal(null)
      fetchDetail()
    } catch (err) {
      alert(err.message)
    } finally {
      setActionLoading(false)
    }
  }

  const handleMarkReady = async () => {
    setActionLoading(true)
    try {
      const res = await authFetch(`/api/authority/complaints/${id}/mark-ready`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ notes: 'Admin completed review and marked ready for Authority Officer.' })
      })
      if (!res.ok) throw new Error('Failed to mark ready.')
      setActionSuccess('Complaint marked Ready for Authority Officer review!')
      fetchDetail()
    } catch (err) {
      alert(err.message)
    } finally {
      setActionLoading(false)
    }
  }

  const handleReject = async () => {
    if (!rejectReason.trim()) {
      alert('Please provide a mandatory justification for rejecting this complaint.')
      return
    }
    setActionLoading(true)
    try {
      const res = await authFetch(`/api/authority/complaints/${id}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: rejectReason })
      })
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}))
        throw new Error(errJson.detail || 'Rejection action failed.')
      }
      setActionSuccess('Complaint rejected.')
      setActiveModal(null)
      fetchDetail()
    } catch (err) {
      alert(err.message)
    } finally {
      setActionLoading(false)
    }
  }

  const handleRequestInfo = async () => {
    if (!infoNotes.trim()) {
      alert('Please describe what additional information or evidence is required.')
      return
    }
    setActionLoading(true)
    try {
      const res = await authFetch(`/api/authority/complaints/${id}/request-info`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ notes: infoNotes })
      })
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}))
        throw new Error(errJson.detail || 'Request info action failed.')
      }
      setActionSuccess('Additional information requested from citizen.')
      setActiveModal(null)
      fetchDetail()
    } catch (err) {
      alert(err.message)
    } finally {
      setActionLoading(false)
    }
  }

  const handleAssignDepartment = async () => {
    if (!selectedDeptId) {
      alert('Please select a municipal department.')
      return
    }
    setActionLoading(true)
    try {
      const res = await authFetch(`/api/authority/complaints/${id}/assign`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          department_id: parseInt(selectedDeptId),
          assigned_to_user_id: selectedOfficerId ? parseInt(selectedOfficerId) : null,
          notes: assignNotes
        })
      })
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}))
        throw new Error(errJson.detail || 'Department assignment failed.')
      }
      setActionSuccess('Complaint assigned successfully!')
      setActiveModal(null)
      fetchDetail()
    } catch (err) {
      alert(err.message)
    } finally {
      setActionLoading(false)
    }
  }

  const handleUpdateStatus = async () => {
    if (!targetStatus) return
    setActionLoading(true)
    try {
      const res = await authFetch(`/api/authority/complaints/${id}/status`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          status: targetStatus,
          notes: statusNotes
        })
      })
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}))
        throw new Error(errJson.detail || 'Status update failed.')
      }
      setActionSuccess(`Administrative status progressed to ${targetStatus}!`)
      setActiveModal(null)
      fetchDetail()
    } catch (err) {
      alert(err.message)
    } finally {
      setActionLoading(false)
    }
  }

  const handleEscalate = async () => {
    if (!escalationReason.trim()) {
      alert('Please specify an escalation justification.')
      return
    }
    setActionLoading(true)
    try {
      const res = await authFetch(`/api/authority/complaints/${id}/escalate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          escalation_level: escalationLevel,
          reason: escalationReason,
          escalated_to: escalatedTo
        })
      })
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}))
        throw new Error(errJson.detail || 'Escalation failed.')
      }
      setActionSuccess(`Escalated to Tier ${escalationLevel} (${escalatedTo})!`)
      setActiveModal(null)
      fetchDetail()
    } catch (err) {
      alert(err.message)
    } finally {
      setActionLoading(false)
    }
  }

  const handleAddInternalNote = async () => {
    if (!newInternalNote.trim()) return
    setActionLoading(true)
    try {
      const res = await authFetch(`/api/authority/complaints/${id}/notes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ notes: newInternalNote })
      })
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}))
        throw new Error(errJson.detail || 'Failed to add note.')
      }
      setNewInternalNote('')
      setActiveModal(null)
      fetchDetail()
    } catch (err) {
      alert(err.message)
    } finally {
      setActionLoading(false)
    }
  }

  if (loading && !complaint) {
    return (
      <AuthorityLayout pageTitle={`File ${id}`} breadcrumbs={['Complaints', id]}>
        <div className="py-24 text-center">
          <RefreshCw className="w-8 h-8 text-[#F36B21] animate-spin mx-auto mb-3" />
          <p className="text-xs text-white/60 font-mono">Loading complaint file {id}...</p>
        </div>
      </AuthorityLayout>
    )
  }

  if (error || !complaint) {
    return (
      <AuthorityLayout pageTitle="Complaint Record" breadcrumbs={['Complaints', id]}>
        <div className="max-w-xl mx-auto px-6 py-20 text-center">
          <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
          <h2 className="text-xl font-bold">Complaint Not Found</h2>
          <p className="text-sm text-white/60 mt-2">{error || 'Unable to locate complaint records.'}</p>
          <Link
            to="/authority/complaints"
            className="mt-6 inline-flex items-center gap-2 px-4 py-2 bg-white/10 hover:bg-white/20 rounded-xl text-xs font-semibold"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Return to Complaints Desk</span>
          </Link>
        </div>
      </AuthorityLayout>
    )
  }

  const latestAI = complaint.ai_analyses?.[0] || null
  const selectedDeptObj = departments.find((d) => d.id === parseInt(selectedDeptId))

  return (
    <AuthorityLayout pageTitle={`Complaint File: ${complaint.complaint_id}`} breadcrumbs={['Complaints', complaint.complaint_id]}>
      <div className="space-y-6 max-w-7xl">
        {/* Back Link & Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-white/5">
          <div className="flex items-center gap-3">
            <Link
              to="/authority/complaints"
              className="p-2 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-white/70 hover:text-white transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
            </Link>
            <div>
              <div className="flex items-center gap-2.5 flex-wrap">
                <h1 className="text-2xl font-bold font-mono tracking-tight text-white">{complaint.complaint_id}</h1>
                {complaint.escalation_level > 0 && (
                  <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold bg-red-500 text-white animate-pulse">
                    <Flame className="w-3.5 h-3.5" />
                    <span>Tier {complaint.escalation_level} Escalated</span>
                  </span>
                )}
                <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                  complaint.verification_status === 'verified'
                    ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                    : complaint.verification_status === 'rejected'
                    ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                    : complaint.verification_status === 'info_requested'
                    ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
                    : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                }`}>
                  Verification: {complaint.verification_status.toUpperCase()}
                </span>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-mono font-medium bg-white/10 text-white/80 border border-white/20">
                  Status: {complaint.admin_status || complaint.status}
                </span>
              </div>
              <p className="text-xs text-white/50 font-mono mt-1">
                Submitted on {complaint.created_at ? formatToIST(complaint.created_at) : ''} via {complaint.submission_channel.toUpperCase()}
              </p>
            </div>
          </div>

          {/* Quick Action Buttons */}
          <div className="flex items-center gap-2 flex-wrap">
            {/* Admin: Mark Ready for Authority Officer */}
            {user?.role === 'admin' && complaint.admin_status !== 'Ready for Authority Officer' && complaint.verification_status === 'pending' && (
              <button
                onClick={handleMarkReady}
                disabled={actionLoading}
                className="px-3.5 py-2 rounded-xl bg-[#18181B] hover:bg-[#27272A] text-white text-xs font-semibold flex items-center gap-1.5 shadow-sm cursor-pointer transition-all"
              >
                <CheckCircle className="w-4 h-4 text-emerald-400" />
                <span>Mark Ready for Officer</span>
              </button>
            )}

            {/* Authority Officer: Verify, Reject, Request Info, Assign, Escalate */}
            {user?.role === 'authority_officer' && (
              <>
                {complaint.verification_status === 'pending' && (
                  <>
                    <button
                      onClick={() => setActiveModal('verify')}
                      className="px-3.5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center gap-1.5 shadow-xs cursor-pointer transition-all"
                    >
                      <CheckCircle className="w-4 h-4" />
                      <span>Accept & Verify</span>
                    </button>
                    <button
                      onClick={() => setActiveModal('reject')}
                      className="px-3.5 py-2 rounded-xl bg-red-600 hover:bg-red-500 text-white text-xs font-semibold flex items-center gap-1.5 shadow-xs cursor-pointer transition-all"
                    >
                      <XCircle className="w-4 h-4" />
                      <span>Reject</span>
                    </button>
                    <button
                      onClick={() => setActiveModal('request_info')}
                      className="px-3.5 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold flex items-center gap-1.5 shadow-xs cursor-pointer transition-all"
                    >
                      <HelpCircle className="w-4 h-4" />
                      <span>Request Info</span>
                    </button>
                  </>
                )}

                <button
                  onClick={() => setActiveModal('assign')}
                  className="px-3.5 py-2 rounded-xl bg-[#102B4E] hover:bg-[#102B4E]/90 text-white text-xs font-semibold flex items-center gap-1.5 shadow-xs cursor-pointer transition-all"
                >
                  <Building2 className="w-4 h-4 text-[#F36B21]" />
                  <span>{complaint.department ? 'Reassign Dept' : 'Assign Dept'}</span>
                </button>

                <button
                  onClick={() => setActiveModal('escalate')}
                  className="px-3.5 py-2 rounded-xl bg-red-50 hover:bg-red-100 border border-red-200 text-red-700 text-xs font-semibold flex items-center gap-1.5 cursor-pointer transition-all"
                >
                  <Flame className="w-4 h-4 text-red-500" />
                  <span>Escalate</span>
                </button>
              </>
            )}

            {/* Department Officer: Update Work Progress */}
            {user?.role === 'department_officer' && (
              <button
                onClick={() => setActiveModal('status')}
                className="px-3.5 py-2 rounded-xl bg-[#18181B] hover:bg-[#27272A] text-white text-xs font-semibold flex items-center gap-1.5 shadow-sm cursor-pointer transition-all"
              >
                <Wrench className="w-4 h-4 text-[#F36B21]" />
                <span>Update Progress</span>
              </button>
            )}

            <button
              onClick={() => setActiveModal('note')}
              className="px-3.5 py-2 rounded-xl bg-[#141722]/85 border border-white/[0.08] text-[#F5F5F5] hover:border-[#F36B21]/40 text-xs font-semibold flex items-center gap-1.5 cursor-pointer transition-all shadow-sm"
            >
              <MessageSquare className="w-4 h-4 text-stone-400" />
              <span>Add Note</span>
            </button>
          </div>
        </div>

        {actionSuccess && (
          <div className="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CheckCircle className="w-4 h-4" />
              <span>{actionSuccess}</span>
            </div>
            <button onClick={() => setActionSuccess(null)} className="text-white/60 hover:text-white">✕</button>
          </div>
        )}

        {/* 2-Column Main Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column (2 spans): Citizen Report, Evidence, AI Analysis, Duplicates */}
          <div className="lg:col-span-2 space-y-6">
            {/* Citizen Report Details */}
            <div className="bg-[#141520]/80 backdrop-blur-2xl border border-white/[0.08] rounded-3xl p-6 md:p-7 shadow-2xl relative overflow-hidden">
              <div className="flex items-center justify-between mb-4">
                <span className="text-xs font-mono uppercase text-[#F36B21] font-bold tracking-wider">
                  Citizen Submission
                </span>
                <span className="text-xs font-mono text-white/50">Tracking: {complaint.tracking_token}</span>
              </div>

              <h2 className="text-lg font-bold text-white mb-2">{complaint.category}</h2>
              <div className="p-4 rounded-2xl bg-black/40 border border-white/5 text-sm text-white/90 leading-relaxed whitespace-pre-wrap">
                {complaint.description}
              </div>

              {/* Citizen Details & Location Meta */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-4 pt-4 border-t border-white/5 text-xs">
                <div>
                  <span className="text-[10px] font-mono text-white/40 uppercase block mb-1">Citizen Information</span>
                  <p className="text-white font-medium">{complaint.citizen_name || 'Anonymous Citizen'}</p>
                  <p className="text-white/60 font-mono mt-0.5">{complaint.citizen_email || 'No email provided'}</p>
                  {complaint.citizen_phone && (
                    <p className="text-white/60 font-mono mt-0.5">{complaint.citizen_phone}</p>
                  )}
                </div>

                <div>
                  <span className="text-[10px] font-mono text-white/40 uppercase block mb-1">Location Details</span>
                  {complaint.latitude && complaint.longitude ? (
                    <div>
                      <div className="flex items-center gap-1.5 font-mono text-white">
                        <MapPin className="w-3.5 h-3.5 text-[#F36B21]" />
                        <span>{complaint.latitude.toFixed(5)}, {complaint.longitude.toFixed(5)}</span>
                      </div>
                      <span className="text-[10px] text-white/40 font-mono block mt-0.5">
                        Source: {complaint.location_source}
                      </span>
                      {complaint.google_maps_url && (
                        <a
                          href={complaint.google_maps_url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 text-[11px] text-[#F36B21] hover:underline mt-1.5"
                        >
                          <span>Open Google Maps</span>
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      )}
                    </div>
                  ) : (
                    <p className="text-white/40 italic font-mono">No coordinates attached.</p>
                  )}
                </div>
              </div>
            </div>

            {/* Evidence Inspection Viewer */}
            <div className="bg-[#141520]/80 backdrop-blur-2xl border border-white/[0.08] rounded-3xl p-6 md:p-7 shadow-2xl">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Eye className="w-4 h-4 text-[#F36B21]" />
                  <h3 className="text-sm font-semibold tracking-wide">Evidence Inspection</h3>
                </div>
                <span className="text-xs text-white/50 font-mono">
                  {complaint.evidence?.length || 0} file(s) uploaded
                </span>
              </div>

              {(!complaint.evidence || complaint.evidence.length === 0) ? (
                <p className="text-center py-6 text-white/40 text-xs font-mono">
                  No photographic or video evidence attached to this report.
                </p>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {complaint.evidence.map((ev) => (
                    <div
                      key={ev.id}
                      className="border border-white/10 rounded-xl overflow-hidden bg-black/40 group relative"
                    >
                      {ev.file_type.includes('video') ? (
                        <div className="p-2">
                          <video
                            controls
                            className="w-full h-48 object-cover rounded-lg bg-black"
                            src={getApiUrl(ev.view_url)}
                          />
                        </div>
                      ) : (
                        <div
                          className="cursor-pointer overflow-hidden h-48 bg-black/60 relative"
                          onClick={() => setSelectedEvidenceView(ev)}
                        >
                          <img
                            src={getApiUrl(ev.view_url)}
                            alt={ev.original_filename}
                            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                          />
                          <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                            <span className="text-xs text-white font-medium bg-black/70 px-3 py-1.5 rounded-lg flex items-center gap-1.5">
                              <Eye className="w-3.5 h-3.5" />
                              <span>Inspect Full Resolution</span>
                            </span>
                          </div>
                        </div>
                      )}

                      <div className="p-3 border-t border-white/5 text-[11px] font-mono text-white/60 flex items-center justify-between">
                        <span className="truncate max-w-[160px]">{ev.original_filename}</span>
                        <span>{Math.round(ev.file_size / 1024)} KB</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Gemini AI Multimodal Analysis Card (Phase 4 Integration) */}
            <div className="bg-[#141520]/80 backdrop-blur-2xl border border-white/[0.08] rounded-3xl p-6 md:p-7 shadow-2xl relative overflow-hidden">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-xl bg-[#F36B21]/20 border border-[#F36B21]/40 flex items-center justify-center">
                    <Cpu className="w-4 h-4 text-[#F36B21]" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-white tracking-wide">Gemini AI Multimodal Analysis</h3>
                    <p className="text-[10px] text-white/50 font-mono">
                      Phase 4 Automated Perception • Advisory Decision Support
                    </p>
                  </div>
                </div>

                <span className="text-[10px] font-mono px-2.5 py-1 rounded-full bg-blue-500/20 text-blue-300 border border-blue-500/30 uppercase">
                  Advisory Only
                </span>
              </div>

              <div className="p-3 rounded-2xl bg-amber-500/10 border border-amber-500/20 text-[11px] text-amber-300 mb-4 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                <span>
                  <strong>Human Oversight Required:</strong> AI analysis provides automated severity and category assessments. Official verification decisions remain the sole responsibility of the municipal officer.
                </span>
              </div>

              {latestAI ? (
                <div className="space-y-4 text-xs">
                  {/* Predicted Category & Severity */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div className="p-3.5 rounded-2xl bg-black/40 border border-white/5">
                      <span className="text-[10px] font-mono text-white/40 uppercase block">Predicted Category</span>
                      <p className="font-semibold text-white mt-0.5">{latestAI.predicted_category || 'N/A'}</p>
                      <span className="text-[10px] text-white/50 font-mono">
                        {latestAI.category_confidence ? `${Math.round(latestAI.category_confidence * 100)}% confidence` : ''}
                      </span>
                    </div>

                    <div className="p-3.5 rounded-2xl bg-black/40 border border-white/5">
                      <span className="text-[10px] font-mono text-white/40 uppercase block">Recommended Severity</span>
                      <p className="font-bold text-amber-300 mt-0.5">{latestAI.recommended_severity || 'Medium'}</p>
                      <span className="text-[10px] text-white/50 font-mono">
                        {latestAI.severity_confidence ? `${Math.round(latestAI.severity_confidence * 100)}% confidence` : ''}
                      </span>
                    </div>

                    <div className="p-3.5 rounded-2xl bg-black/40 border border-white/5">
                      <span className="text-[10px] font-mono text-white/40 uppercase block">Evidence Relevance</span>
                      <p className="font-semibold text-emerald-400 mt-0.5">{latestAI.evidence_relevance || 'Relevant'}</p>
                      <span className="text-[10px] text-white/50 font-mono">
                        Score: {latestAI.relevance_score || 85}/100
                      </span>
                    </div>

                    <div className="p-3.5 rounded-2xl bg-black/40 border border-white/5">
                      <span className="text-[10px] font-mono text-white/40 uppercase block">Image Clarity</span>
                      <p className="font-semibold text-white mt-0.5">{latestAI.image_quality || 'Clear'}</p>
                      <span className="text-[10px] text-white/50 font-mono">
                        Clarity: {latestAI.clarity_score || 80}/100
                      </span>
                    </div>
                  </div>

                  {/* Visible Problem & AI Reasoning */}
                  {latestAI.visible_problem && (
                    <div className="p-4 rounded-2xl bg-black/40 border border-white/5">
                      <span className="text-[10px] font-mono text-white/40 uppercase block mb-1">
                        Detected Physical Problem
                      </span>
                      <p className="text-white/80 leading-relaxed">{latestAI.visible_problem}</p>
                    </div>
                  )}

                  {latestAI.reasoning && (
                    <div className="p-4 rounded-2xl bg-black/40 border border-white/5">
                      <span className="text-[10px] font-mono text-white/40 uppercase block mb-1">
                        Severity & Hazard Justification
                      </span>
                      <p className="text-white/70 leading-relaxed">{latestAI.reasoning}</p>
                    </div>
                  )}
                </div>
              ) : (
                <div className="py-6 text-center text-white/40 font-mono text-xs">
                  No automated AI analysis available for this complaint.
                </div>
              )}
            </div>

            {/* Duplicate Matches & Deduplication (Phase 5 Integration) */}
            <div className="bg-[#141520]/80 backdrop-blur-2xl border border-white/[0.08] rounded-3xl p-6 md:p-7 shadow-2xl">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Layers className="w-4 h-4 text-[#F36B21]" />
                  <h3 className="text-sm font-semibold tracking-wide">Duplicate Detection & Clustering</h3>
                </div>
                <Link
                  to="/duplicates"
                  className="text-xs text-[#F36B21] hover:underline font-medium flex items-center gap-1"
                >
                  <span>Open Review Desk</span>
                  <ExternalLink className="w-3 h-3" />
                </Link>
              </div>

              {(!complaint.duplicate_matches || complaint.duplicate_matches.length === 0) ? (
                <p className="text-xs text-white/40 font-mono py-2">
                  No existing duplicate physical issues detected in close spatial proximity.
                </p>
              ) : (
                <div className="space-y-3">
                  {complaint.duplicate_matches.map((dm) => (
                    <div key={dm.id} className="p-4 rounded-2xl bg-white/5 border border-white/10 text-xs">
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="font-mono font-bold text-white">
                          Candidate Issue: {dm.candidate_physical_issue_id}
                        </span>
                        <span className="font-mono text-xs font-bold text-[#F36B21] bg-[#F36B21]/10 px-2.5 py-0.5 rounded-full">
                          {Math.round(dm.similarity_score * 100)}% Match
                        </span>
                      </div>
                      <p className="text-white/70 leading-relaxed">{dm.matching_explanation}</p>
                      <div className="mt-2 pt-2 border-t border-white/5 flex items-center justify-between text-[10px] text-white/40 font-mono">
                        <span>Confidence: {dm.confidence_level.toUpperCase()}</span>
                        <span>Review: {dm.review_status.toUpperCase()}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Right Column (1 span): Administrative Decision & Workflow State */}
          <div className="space-y-6">
            {/* Human Verification Status Box */}
            <div className="bg-[#141520]/80 backdrop-blur-2xl border border-white/[0.08] rounded-3xl p-6 shadow-2xl">
              <span className="text-[10px] font-mono uppercase text-white/40 block mb-2 font-semibold">
                Human Verification Record
              </span>

              <div className="space-y-2 text-xs">
                <div className="flex items-center justify-between py-1 border-b border-white/5">
                  <span className="text-white/60">Status:</span>
                  <span className="font-bold text-white uppercase font-mono">{complaint.verification_status}</span>
                </div>
                {complaint.verified_by_name && (
                  <div className="flex items-center justify-between py-1 border-b border-white/5">
                    <span className="text-white/60">Verified By:</span>
                    <span className="text-white font-medium">{complaint.verified_by_name}</span>
                  </div>
                )}
                {complaint.verified_at && (
                  <div className="flex items-center justify-between py-1 border-b border-white/5">
                    <span className="text-white/60">Verified At:</span>
                    <span className="text-white font-mono text-[11px]">
                      {formatToIST(complaint.verified_at)}
                    </span>
                  </div>
                )}
                {complaint.rejection_reason && (
                  <div className="py-2">
                    <span className="text-red-400 font-semibold block mb-1">Rejection Reason:</span>
                    <p className="p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-300 text-[11px] leading-relaxed">
                      {complaint.rejection_reason}
                    </p>
                  </div>
                )}
                {complaint.info_request_notes && (
                  <div className="py-2">
                    <span className="text-blue-400 font-semibold block mb-1">Requested Citizen Information:</span>
                    <p className="p-3 rounded-xl bg-blue-500/10 border border-blue-500/20 text-blue-300 text-[11px] leading-relaxed">
                      {complaint.info_request_notes}
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* Department Assignment Box */}
            <div className="bg-[#141520]/80 backdrop-blur-2xl border border-white/[0.08] rounded-3xl p-6 shadow-2xl">
              <div className="flex items-center justify-between mb-3">
                <span className="text-[10px] font-mono uppercase text-white/40 font-semibold">
                  Assigned Department
                </span>
                {complaint.department && (
                  <span className="text-xs font-mono font-bold text-[#F36B21]">
                    {complaint.department.code}
                  </span>
                )}
              </div>

              {complaint.department ? (
                <div className="space-y-2 text-xs">
                  <p className="font-bold text-white text-sm">{complaint.department.name}</p>
                  {complaint.assigned_user && (
                    <div className="flex items-center gap-1.5 text-white/70">
                      <User className="w-3.5 h-3.5 text-white/40" />
                      <span>Officer: {complaint.assigned_user.full_name}</span>
                    </div>
                  )}
                  {complaint.assigned_at && (
                    <p className="text-[10px] text-white/40 font-mono">
                      Assigned: {formatToIST(complaint.assigned_at)}
                    </p>
                  )}
                  {complaint.assignment_notes && (
                    <div className="mt-2 p-2.5 rounded-xl bg-white/5 border border-white/5 text-[11px] text-white/70">
                      <span className="text-white/40 block text-[9px] uppercase font-mono">Notes:</span>
                      {complaint.assignment_notes}
                    </div>
                  )}
                </div>
              ) : (
                <div className="py-4 text-center">
                  <p className="text-xs text-white/40 italic font-mono mb-3">No department assigned yet.</p>
                  <button
                    onClick={() => setActiveModal('assign')}
                    className="px-3.5 py-2 rounded-xl bg-[#F36B21] text-white text-xs font-semibold cursor-pointer shadow-lg shadow-[#F36B21]/20"
                  >
                    Assign Department
                  </button>
                </div>
              )}
            </div>

            {/* Escalation Record */}
            {complaint.escalation_level > 0 && (
              <div className="bg-red-500/10 border border-red-500/30 rounded-3xl p-6 shadow-2xl backdrop-blur-2xl">
                <div className="flex items-center gap-2 mb-2">
                  <Flame className="w-4 h-4 text-red-400" />
                  <span className="text-xs font-bold text-red-300 font-mono uppercase">
                    Tier {complaint.escalation_level} Escalation Active
                  </span>
                </div>
                <div className="text-xs space-y-1.5 text-red-200">
                  <p><strong>Escalated To:</strong> {complaint.escalated_to || 'Municipal Commissioner'}</p>
                  {complaint.escalated_at && (
                    <p className="font-mono text-[11px] text-red-300/70">
                      Time: {formatToIST(complaint.escalated_at)}
                    </p>
                  )}
                  <p className="mt-2 p-3 rounded-2xl bg-red-950/40 border border-red-500/20 text-[11px] leading-relaxed">
                    <strong>Reason:</strong> {complaint.escalation_reason}
                  </p>
                </div>
              </div>
            )}

            {/* Internal Staff Notes */}
            <div className="bg-[#141520]/80 backdrop-blur-2xl border border-white/[0.08] rounded-3xl p-6 shadow-2xl">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-1.5">
                  <Lock className="w-3.5 h-3.5 text-white/40" />
                  <span className="text-[10px] font-mono uppercase text-white/40 font-semibold">
                    Staff Internal Notes
                  </span>
                </div>
                <button
                  onClick={() => setActiveModal('note')}
                  className="text-[11px] text-[#F36B21] hover:underline font-medium"
                >
                  + Add Note
                </button>
              </div>

              {complaint.internal_notes ? (
                <div className="p-3.5 rounded-2xl bg-black/40 border border-white/5 text-xs text-white/80 whitespace-pre-wrap font-mono leading-relaxed max-h-48 overflow-y-auto">
                  {complaint.internal_notes}
                </div>
              ) : (
                <p className="text-center py-4 text-white/30 text-xs font-mono">
                  No internal staff comments recorded.
                </p>
              )}
            </div>

            {/* Audit History Timeline */}
            <div className="bg-[#141520]/80 backdrop-blur-2xl border border-white/[0.08] rounded-3xl p-6 shadow-2xl">
              <span className="text-[10px] font-mono uppercase text-white/40 block mb-3 font-semibold">
                Full Audit Trail ({complaint.audit_events?.length || 0})
              </span>

              <div className="space-y-3 max-h-80 overflow-y-auto pr-1">
                {(complaint.audit_events || []).map((ev) => (
                  <div key={ev.id} className="relative pl-4 border-l border-white/10 text-xs space-y-0.5">
                    <span className="absolute -left-1.5 top-1 w-2.5 h-2.5 rounded-full bg-[#F36B21]/60" />
                    <div className="flex items-center justify-between text-[10px] text-white/40 font-mono">
                      <span className="uppercase text-white/60">{ev.event_type}</span>
                      <span>{ev.created_at ? formatToIST(ev.created_at) : ''}</span>
                    </div>
                    <p className="text-white/80 leading-snug">{ev.description}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* --- Action Modals --- */}

      {/* 1. Verify Modal */}
      {activeModal === 'verify' && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
          <div className="bg-[#141520]/95 backdrop-blur-2xl border border-white/[0.12] rounded-3xl max-w-md w-full p-6 md:p-7 space-y-4 shadow-2xl">
            <div className="flex items-center gap-2 text-emerald-400">
              <CheckCircle className="w-5 h-5" />
              <h3 className="text-base font-bold text-white">Verify Civic Complaint</h3>
            </div>
            <p className="text-xs text-white/70 leading-relaxed">
              Confirm that this report represents an authentic, valid civic infrastructure grievance. Once verified, it can be assigned to municipal execution teams.
            </p>
            <div>
              <label className="block text-[11px] font-mono uppercase text-white/50 mb-1">
                Verification Notes (Optional)
              </label>
              <textarea
                value={verifyNotes}
                onChange={(e) => setVerifyNotes(e.target.value)}
                placeholder="e.g. Inspected geotagged photo, potholes confirmed on main arterial road..."
                rows={3}
                className="w-full p-3 bg-black/40 border border-white/10 rounded-2xl text-xs text-white focus:outline-none focus:border-emerald-500"
              />
            </div>
            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                onClick={() => setActiveModal(null)}
                className="px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-xs font-semibold text-white/70 cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleVerify}
                disabled={actionLoading}
                className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-xs font-semibold text-white shadow-md shadow-emerald-600/20 cursor-pointer"
              >
                {actionLoading ? 'Processing...' : 'Confirm Verification'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 2. Reject Modal */}
      {activeModal === 'reject' && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
          <div className="bg-[#141520]/95 backdrop-blur-2xl border border-white/[0.12] rounded-3xl max-w-md w-full p-6 md:p-7 space-y-4 shadow-2xl">
            <div className="flex items-center gap-2 text-red-400">
              <XCircle className="w-5 h-5" />
              <h3 className="text-base font-bold text-white">Reject Complaint</h3>
            </div>
            <p className="text-xs text-white/70 leading-relaxed">
              Mandatory justification is required. This justification will be logged in the public audit trail.
            </p>
            <div>
              <label className="block text-[11px] font-mono uppercase text-white/50 mb-1">
                Rejection Reason (Required) *
              </label>
              <textarea
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="e.g. Out of municipal jurisdiction; private property; prank submission..."
                rows={3}
                required
                className="w-full p-3 bg-black/40 border border-white/10 rounded-2xl text-xs text-white focus:outline-none focus:border-red-500"
              />
            </div>
            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                onClick={() => setActiveModal(null)}
                className="px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-xs font-semibold text-white/70 cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleReject}
                disabled={actionLoading}
                className="px-4 py-2 rounded-xl bg-red-600 hover:bg-red-500 text-xs font-semibold text-white shadow-md shadow-red-600/20 cursor-pointer"
              >
                {actionLoading ? 'Processing...' : 'Confirm Rejection'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 3. Request Info Modal */}
      {activeModal === 'request_info' && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
          <div className="bg-[#141520]/95 backdrop-blur-2xl border border-white/[0.12] rounded-3xl max-w-md w-full p-6 md:p-7 space-y-4 shadow-2xl">
            <div className="flex items-center gap-2 text-blue-400">
              <HelpCircle className="w-5 h-5" />
              <h3 className="text-base font-bold text-white">Request Additional Information</h3>
            </div>
            <p className="text-xs text-white/70 leading-relaxed">
              Specify what additional landmark details, clearer daytime photos, or coordinates are needed from the citizen.
            </p>
            <div>
              <label className="block text-[11px] font-mono uppercase text-white/50 mb-1">
                Information Request (Required) *
              </label>
              <textarea
                value={infoNotes}
                onChange={(e) => setInfoNotes(e.target.value)}
                placeholder="e.g. Please provide the exact cross-street or pillar number..."
                rows={3}
                required
                className="w-full p-3 bg-black/40 border border-white/10 rounded-2xl text-xs text-white focus:outline-none focus:border-blue-500"
              />
            </div>
            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                onClick={() => setActiveModal(null)}
                className="px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-xs font-semibold text-white/70 cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleRequestInfo}
                disabled={actionLoading}
                className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-xs font-semibold text-white shadow-md shadow-blue-600/20 cursor-pointer"
              >
                {actionLoading ? 'Processing...' : 'Submit Request'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 4. Assign Department Modal */}
      {activeModal === 'assign' && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
          <div className="bg-[#141520]/95 backdrop-blur-2xl border border-white/[0.12] rounded-3xl max-w-md w-full p-6 md:p-7 space-y-4 shadow-2xl">
            <div className="flex items-center gap-2 text-[#F36B21]">
              <Building2 className="w-5 h-5" />
              <h3 className="text-base font-bold text-white">Assign Municipal Department</h3>
            </div>

            <div>
              <label className="block text-[11px] font-mono uppercase text-white/50 mb-1">
                Select Department *
              </label>
              <select
                value={selectedDeptId}
                onChange={(e) => {
                  setSelectedDeptId(e.target.value)
                  setSelectedOfficerId('')
                }}
                className="w-full p-3 bg-black/40 border border-white/10 rounded-2xl text-xs text-white focus:outline-none focus:border-[#F36B21]"
              >
                <option value="">-- Choose Municipal Division --</option>
                {departments.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.code} - {d.name} (SLA: {d.sla_days} days)
                  </option>
                ))}
              </select>
            </div>

            {selectedDeptObj?.users?.length > 0 && (
              <div>
                <label className="block text-[11px] font-mono uppercase text-white/50 mb-1">
                  Assign Lead Officer (Optional)
                </label>
                <select
                  value={selectedOfficerId}
                  onChange={(e) => setSelectedOfficerId(e.target.value)}
                  className="w-full p-3 bg-black/40 border border-white/10 rounded-2xl text-xs text-white focus:outline-none focus:border-[#F36B21]"
                >
                  <option value="">-- Any Available Department Officer --</option>
                  {selectedDeptObj.users.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.full_name} ({u.role})
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div>
              <label className="block text-[11px] font-mono uppercase text-white/50 mb-1">
                Assignment Instructions
              </label>
              <textarea
                value={assignNotes}
                onChange={(e) => setAssignNotes(e.target.value)}
                placeholder="e.g. Priority dispatch needed before weekend market congestion..."
                rows={2}
                className="w-full p-3 bg-black/40 border border-white/10 rounded-2xl text-xs text-white focus:outline-none focus:border-[#F36B21]"
              />
            </div>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                onClick={() => setActiveModal(null)}
                className="px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-xs font-semibold text-white/70 cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleAssignDepartment}
                disabled={actionLoading}
                className="px-4 py-2 rounded-xl bg-[#F36B21] hover:bg-[#F36B21]/90 text-xs font-semibold text-white shadow-md shadow-[#F36B21]/20 cursor-pointer"
              >
                {actionLoading ? 'Assigning...' : 'Dispatch to Department'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 5. Update Status Modal */}
      {activeModal === 'status' && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
          <div className="bg-[#141520]/95 backdrop-blur-2xl border border-white/[0.12] rounded-3xl max-w-md w-full p-6 md:p-7 space-y-4 shadow-2xl">
            <div className="flex items-center gap-2 text-white">
              <RefreshCw className="w-5 h-5 text-[#F36B21]" />
              <h3 className="text-base font-bold text-white">Update Administrative Status</h3>
            </div>

            <div>
              <label className="block text-[11px] font-mono uppercase text-white/50 mb-1">
                Progress Status *
              </label>
              <select
                value={targetStatus}
                onChange={(e) => setTargetStatus(e.target.value)}
                className="w-full p-3 bg-black/40 border border-white/10 rounded-2xl text-xs text-white focus:outline-none focus:border-[#F36B21]"
              >
                <option value="Received">Received</option>
                <option value="Pending Verification">Pending Verification</option>
                <option value="Verified">Verified</option>
                <option value="Awaiting Department Assignment">Awaiting Department Assignment</option>
                <option value="Assigned">Assigned</option>
                <option value="In Progress">In Progress (Field Work Active)</option>
                <option value="Resolved">Resolved (Work Completed)</option>
                <option value="Rejected">Rejected</option>
                <option value="Escalated">Escalated</option>
              </select>
            </div>

            <div>
              <label className="block text-[11px] font-mono uppercase text-white/50 mb-1">
                Progress Notes
              </label>
              <textarea
                value={statusNotes}
                onChange={(e) => setStatusNotes(e.target.value)}
                placeholder="e.g. Patchwork completed by asphalt crew; curing in progress..."
                rows={3}
                className="w-full p-3 bg-black/40 border border-white/10 rounded-2xl text-xs text-white focus:outline-none focus:border-[#F36B21]"
              />
            </div>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                onClick={() => setActiveModal(null)}
                className="px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-xs font-semibold text-white/70 cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleUpdateStatus}
                disabled={actionLoading}
                className="px-4 py-2 rounded-xl bg-[#F36B21] hover:bg-[#F36B21]/90 text-xs font-semibold text-white shadow-md shadow-[#F36B21]/20 cursor-pointer"
              >
                {actionLoading ? 'Updating...' : 'Update Status'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 6. Escalate Modal */}
      {activeModal === 'escalate' && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
          <div className="bg-[#141520]/95 backdrop-blur-2xl border border-red-500/30 rounded-3xl max-w-md w-full p-6 md:p-7 space-y-4 shadow-2xl">
            <div className="flex items-center gap-2 text-red-400">
              <Flame className="w-5 h-5 animate-pulse" />
              <h3 className="text-base font-bold text-white">Escalate Civic Complaint</h3>
            </div>
            <p className="text-xs text-white/70 leading-relaxed">
              Escalating flags this complaint into the executive intervention queue and alerts higher municipal leadership.
            </p>

            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setEscalationLevel(1)}
                className={`p-3 rounded-2xl border text-xs font-semibold text-left transition-colors cursor-pointer ${
                  escalationLevel === 1
                    ? 'bg-red-500/20 border-red-500 text-white'
                    : 'bg-white/5 border-white/10 text-white/60'
                }`}
              >
                <span className="block font-bold">Tier 1</span>
                <span className="text-[10px] text-white/40">Division Head / EE</span>
              </button>
              <button
                type="button"
                onClick={() => setEscalationLevel(2)}
                className={`p-3 rounded-2xl border text-xs font-semibold text-left transition-colors cursor-pointer ${
                  escalationLevel === 2
                    ? 'bg-red-500/20 border-red-500 text-white'
                    : 'bg-white/5 border-white/10 text-white/60'
                }`}
              >
                <span className="block font-bold text-red-400">Tier 2</span>
                <span className="text-[10px] text-white/40">Municipal Commissioner</span>
              </button>
            </div>

            <div>
              <label className="block text-[11px] font-mono uppercase text-white/50 mb-1">
                Designated Higher Authority
              </label>
              <input
                type="text"
                value={escalatedTo}
                onChange={(e) => setEscalatedTo(e.target.value)}
                className="w-full p-3 bg-black/40 border border-white/10 rounded-2xl text-xs text-white focus:outline-none focus:border-red-500"
              />
            </div>

            <div>
              <label className="block text-[11px] font-mono uppercase text-white/50 mb-1">
                Escalation Justification *
              </label>
              <textarea
                value={escalationReason}
                onChange={(e) => setEscalationReason(e.target.value)}
                placeholder="e.g. Unresolved safety hazard causing vehicular accidents; SLA exceeded by 5 days..."
                rows={3}
                required
                className="w-full p-3 bg-black/40 border border-white/10 rounded-2xl text-xs text-white focus:outline-none focus:border-red-500"
              />
            </div>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                onClick={() => setActiveModal(null)}
                className="px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-xs font-semibold text-white/70 cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleEscalate}
                disabled={actionLoading}
                className="px-4 py-2 rounded-xl bg-red-600 hover:bg-red-500 text-xs font-semibold text-white shadow-md shadow-red-600/30 cursor-pointer"
              >
                {actionLoading ? 'Escalating...' : 'Trigger Escalation'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 7. Internal Note Modal */}
      {activeModal === 'note' && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
          <div className="bg-[#141520]/95 backdrop-blur-2xl border border-white/[0.12] rounded-3xl max-w-md w-full p-6 md:p-7 space-y-4 shadow-2xl">
            <div className="flex items-center gap-2 text-white">
              <Lock className="w-4 h-4 text-[#F36B21]" />
              <h3 className="text-base font-bold text-white">Add Staff Internal Note</h3>
            </div>
            <p className="text-xs text-white/60">
              Private administrative note. This note will never be exposed to the citizen.
            </p>
            <div>
              <textarea
                value={newInternalNote}
                onChange={(e) => setNewInternalNote(e.target.value)}
                placeholder="Enter confidential notes, contractor details, or resolution instructions..."
                rows={4}
                className="w-full p-3 bg-black/40 border border-white/10 rounded-2xl text-xs text-white focus:outline-none focus:border-[#F36B21]"
              />
            </div>
            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                onClick={() => setActiveModal(null)}
                className="px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-xs font-semibold text-white/70 cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleAddInternalNote}
                disabled={actionLoading || !newInternalNote.trim()}
                className="px-4 py-2 rounded-xl bg-[#F36B21] hover:bg-[#F36B21]/90 text-xs font-semibold text-white cursor-pointer shadow-md shadow-[#F36B21]/20"
              >
                {actionLoading ? 'Saving...' : 'Save Note'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 8. Full Resolution Evidence Lightbox */}
      {selectedEvidenceView && (
        <div
          className="fixed inset-0 z-50 bg-black/90 backdrop-blur-md flex items-center justify-center p-4 cursor-pointer"
          onClick={() => setSelectedEvidenceView(null)}
        >
          <div
            className="max-w-4xl max-h-[90vh] bg-[#141520]/95 backdrop-blur-2xl rounded-3xl overflow-hidden border border-white/20 p-3 cursor-default flex flex-col shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between p-3 border-b border-white/10 text-xs text-white/80 font-mono">
              <span>{selectedEvidenceView.original_filename}</span>
              <button
                onClick={() => setSelectedEvidenceView(null)}
                className="text-white/60 hover:text-white px-2.5 py-1 rounded-xl bg-white/10 cursor-pointer"
              >
                Close ✕
              </button>
            </div>
            <div className="p-3 overflow-auto flex items-center justify-center max-h-[75vh]">
              <img
                src={`${getApiUrl(selectedEvidenceView.view_url)}${token ? `?token=${encodeURIComponent(token)}` : ''}`}
                alt={selectedEvidenceView.original_filename}
                className="max-h-full max-w-full object-contain rounded-2xl"
              />
            </div>
          </div>
        </div>
      )}
    </AuthorityLayout>
  )
}

