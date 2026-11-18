import React, { useState, useEffect } from 'react'
import { useParams, useLocation, useNavigate, Link } from 'react-router-dom'
import {
  ArrowLeft, MapPin, Clock, Calendar, CheckCircle2, AlertTriangle,
  Flame, Building2, User, Send, ExternalLink, Wrench, FileText,
  CheckCircle, RefreshCw, AlertCircle, Eye, UploadCloud, MessageSquare,
  Shield, Layers, ChevronRight, X, Image as ImageIcon
} from 'lucide-react'
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useAuth } from '../../context/AuthContext'
import { getApiUrl } from '../../config/api'
import AuthorityLayout from '../../components/AuthorityLayout'
import { formatToIST, formatISTDateOnly, formatISTTimeOnly } from '../../utils/dateTime'
import { resolveDepartment, saveDepartmentContext } from '../../utils/departmentContext'

const workOrderMarkerIcon = new L.Icon({
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
})

export default function DepartmentWorkOrderDetailPage() {
  const { id } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  const { user, isAuthenticated, authFetch, token } = useAuth()

  const [complaint, setComplaint] = useState(null)
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(false)
  const [error, setError] = useState(null)
  const [forbidden, setForbidden] = useState(false)
  const [forbiddenDetail, setForbiddenDetail] = useState('')
  const [actionSuccess, setActionSuccess] = useState(null)

  // Modals & Action States
  const [activeModal, setActiveModal] = useState(null) // 'status', 'notes', 'evidence', 'evidence_view', 'submit_resolution'
  const [targetStatus, setTargetStatus] = useState('In Progress')
  const [statusNotes, setStatusNotes] = useState('')
  const [newInspectionNote, setNewInspectionNote] = useState('')
  const [evidenceFile, setEvidenceFile] = useState(null)
  const [evidenceCaption, setEvidenceCaption] = useState('')
  const [selectedEvidenceView, setSelectedEvidenceView] = useState(null)

  // Phase 8 Resolution Submission States
  const [resWorkDesc, setResWorkDesc] = useState('')
  const [resRepairAction, setResRepairAction] = useState('')
  const [resMaterials, setResMaterials] = useState('')
  const [resAfterPhotoUrl, setResAfterPhotoUrl] = useState('')
  const [resFieldNotes, setResFieldNotes] = useState('')

  // Department context resolution
  const searchParams = new URLSearchParams(location.search)
  const queryDept = searchParams.get('dept')
  const currentDept = resolveDepartment(queryDept || complaint?.department?.id, user)

  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/authority/login')
      return
    }
    fetchWorkOrderDetail()
  }, [id, isAuthenticated, navigate])

  const fetchWorkOrderDetail = async () => {
    setLoading(true)
    setError(null)
    setForbidden(false)
    try {
      const res = await authFetch(`/api/authority/complaints/${id}`)
      if (res.status === 403) {
        const errJson = await res.json().catch(() => ({}))
        setForbidden(true)
        setForbiddenDetail(errJson.detail || 'Access forbidden: You do not have permission to inspect this department work order.')
        return
      }
      if (res.status === 404) {
        throw new Error(`Work order '${id}' was not found in municipal records.`)
      }
      if (!res.ok) {
        throw new Error(`Failed to load work order ${id} (Status ${res.status}).`)
      }

      const data = await res.json()
      setComplaint(data)

      // Ensure active department in context matches the work order department
      if (data.department) {
        const resolved = resolveDepartment(data.department.id, user)
        saveDepartmentContext(resolved)
      }
      setTargetStatus(data.admin_status || 'In Progress')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  // --- Department Officer Authorized Actions ---

  // 1. Update Work Progress Status
  const handleUpdateStatus = async (statusOverride, notesOverride) => {
    setActionLoading(true)
    setActionSuccess(null)
    try {
      const statusToApply = statusOverride || targetStatus
      const notesToApply = notesOverride !== undefined ? notesOverride : statusNotes

      const res = await authFetch(`/api/authority/complaints/${id}/status`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          status: statusToApply,
          notes: notesToApply
        })
      })

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}))
        throw new Error(errJson.detail || 'Failed to update work order status.')
      }

      setActionSuccess(`Work order status updated to "${statusToApply}" successfully.`)
      setActiveModal(null)
      setStatusNotes('')
      fetchWorkOrderDetail()
    } catch (err) {
      alert(`Error: ${err.message}`)
    } finally {
      setActionLoading(false)
    }
  }

  // 2. Add Field Inspection Note
  const handleAddInspectionNote = async (e) => {
    e.preventDefault()
    if (!newInspectionNote.trim()) return
    setActionLoading(true)
    setActionSuccess(null)
    try {
      const res = await authFetch(`/api/authority/complaints/${id}/notes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ notes: newInspectionNote.trim() })
      })

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}))
        throw new Error(errJson.detail || 'Failed to record inspection notes.')
      }

      setActionSuccess('Field inspection note recorded into work order file.')
      setActiveModal(null)
      setNewInspectionNote('')
      fetchWorkOrderDetail()
    } catch (err) {
      alert(`Error: ${err.message}`)
    } finally {
      setActionLoading(false)
    }
  }

  // 3. Upload Field Inspection Evidence
  const handleUploadEvidence = async (e) => {
    e.preventDefault()
    if (!evidenceFile) {
      alert('Please select an inspection photo or evidence file.')
      return
    }

    setActionLoading(true)
    setActionSuccess(null)
    try {
      const formData = new FormData()
      formData.append('file', evidenceFile)
      if (evidenceCaption.trim()) {
        formData.append('caption', evidenceCaption.trim())
      }

      const res = await authFetch(`/api/authority/complaints/${id}/evidence`, {
        method: 'POST',
        body: formData
      })

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}))
        throw new Error(errJson.detail || 'Failed to upload field inspection evidence.')
      }

      setActionSuccess('Field inspection evidence uploaded and verified.')
      setActiveModal(null)
      setEvidenceFile(null)
      setEvidenceCaption('')
      fetchWorkOrderDetail()
    } catch (err) {
      alert(`Error: ${err.message}`)
    } finally {
      setActionLoading(false)
    }
  }

  // 4. Quick Action: Start Inspection
  const handleStartInspection = async () => {
    await handleUpdateStatus('In Progress', 'Field engineer commenced on-site physical inspection.')
  }

  // Phase 8: Comprehensive Resolution Submission Handler
  const handleOpenResolutionModal = () => {
    setResWorkDesc(`Completed field repairs for ${complaint?.category || 'reported issue'}`)
    setResRepairAction('')
    setResMaterials('')
    setResAfterPhotoUrl(complaint?.evidence_files?.[0]?.file_url || '/assets/dept_rpw.jpg')
    setResFieldNotes('')
    setActiveModal('submit_resolution')
  }

  const handleSubmitResolutionDossier = async (e) => {
    if (e) e.preventDefault()
    if (!resRepairAction.trim()) {
      alert('Please specify the repair action taken.')
      return
    }
    setActionLoading(true)
    setActionSuccess(null)
    try {
      const payload = {
        work_description: resWorkDesc.trim() || 'Field repair completed',
        repair_action_taken: resRepairAction.trim(),
        materials_used: resMaterials.trim() || 'Standard municipal repair materials',
        field_notes: resFieldNotes.trim(),
        after_photo_urls: resAfterPhotoUrl ? [resAfterPhotoUrl.trim()] : []
      }
      const res = await authFetch(`/api/authority/complaints/${complaint.complaint_id}/resolution/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}))
        throw new Error(errJson.detail || 'Failed to submit resolution dossier.')
      }
      setActionSuccess('Resolution dossier submitted! Complaint is now awaiting Authority Officer verification.')
      setActiveModal(null)
      fetchWorkOrderDetail()
    } catch (err) {
      alert(`Submission Error: ${err.message}`)
    } finally {
      setActionLoading(false)
    }
  }

  // Back Navigation preserving department context
  const targetDeptId = complaint?.department?.id || currentDept.id
  const backUrl = `/authority?dept=${targetDeptId}`

  // --- Render Loading State ---
  if (loading) {
    return (
      <AuthorityLayout pageTitle="Loading Work Order" breadcrumbs={['Department Operations', currentDept.name, 'Work Order']}>
        <div className="max-w-xl mx-auto px-6 py-28 text-center">
          <RefreshCw className="w-9 h-9 text-[#F36B21] animate-spin mx-auto mb-3" />
          <h2 className="text-base font-bold text-[#F5F5F5]">Loading Work Order {id}...</h2>
          <p className="text-xs text-[#A1A1AA] mt-1 font-mono">Synchronizing division dispatch records and evidence</p>
        </div>
      </AuthorityLayout>
    )
  }

  // --- Render 403 Forbidden State (Cross-Department Isolation) ---
  if (forbidden) {
    return (
      <AuthorityLayout pageTitle="Unauthorized Access" breadcrumbs={['Department Operations', 'Access Restricted']}>
        <div className="max-w-xl mx-auto px-6 py-20 text-center">
          <div className="w-16 h-16 rounded-2xl bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-amber-400 mx-auto mb-4">
            <Shield className="w-8 h-8" />
          </div>
          <h2 className="text-xl font-bold text-[#F5F5F5]">Department Authorization Required</h2>
          <p className="text-xs text-[#A1A1AA] mt-2 leading-relaxed">
            {forbiddenDetail}
          </p>
          <div className="mt-4 p-3 rounded-xl bg-[#141722]/85 border border-white/[0.08] text-xs text-[#A1A1AA] font-mono">
            Work Order: <span className="text-[#F5F5F5] font-bold">{id}</span>
          </div>
          <div className="mt-6 flex items-center justify-center gap-3">
            <Link
              to={backUrl}
              className="inline-flex items-center gap-2 px-4 py-2.5 bg-[#F36B21] hover:bg-[#E05A10] text-white rounded-xl text-xs font-semibold shadow-md transition-all"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>Back to {currentDept.name} Dashboard</span>
            </Link>
            <Link
              to="/authority/select-department"
              className="inline-flex items-center gap-2 px-4 py-2.5 bg-white/[0.08] hover:bg-white/[0.15] text-[#F5F5F5] rounded-xl text-xs font-semibold border border-white/[0.08] transition-all"
            >
              <Layers className="w-4 h-4" />
              <span>Switch Division</span>
            </Link>
          </div>
        </div>
      </AuthorityLayout>
    )
  }

  // --- Render 404 / Error State ---
  if (error || !complaint) {
    return (
      <AuthorityLayout pageTitle="Work Order Not Found" breadcrumbs={['Department Operations', currentDept.name, id]}>
        <div className="max-w-xl mx-auto px-6 py-20 text-center">
          <div className="w-16 h-16 rounded-2xl bg-red-500/15 border border-red-500/30 flex items-center justify-center text-red-400 mx-auto mb-4">
            <AlertCircle className="w-8 h-8" />
          </div>
          <h2 className="text-xl font-bold text-[#F5F5F5]">Work Order Record Not Found</h2>
          <p className="text-xs text-[#A1A1AA] mt-2">{error || 'Unable to locate work order record in municipal database.'}</p>
          <div className="mt-6 flex items-center justify-center gap-3">
            <button
              onClick={fetchWorkOrderDetail}
              className="inline-flex items-center gap-2 px-4 py-2.5 bg-[#F36B21] hover:bg-[#E05A10] text-white rounded-xl text-xs font-semibold cursor-pointer shadow-md transition-all"
            >
              <RefreshCw className="w-4 h-4" />
              <span>Retry</span>
            </button>
            <Link
              to={backUrl}
              className="inline-flex items-center gap-2 px-4 py-2.5 bg-white/[0.08] hover:bg-white/[0.15] text-[#F5F5F5] rounded-xl text-xs font-semibold border border-white/[0.08] transition-all"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>Back to Assigned Work</span>
            </Link>
          </div>
        </div>
      </AuthorityLayout>
    )
  }

  const deptMeta = resolveDepartment(complaint.department?.id || currentDept.id, user)
  const isResolvedOrSubmitted = ['Resolution Submitted', 'Resolved'].includes(complaint.admin_status)

  return (
    <AuthorityLayout
      pageTitle={`Work Order: ${complaint.complaint_id}`}
      breadcrumbs={['Department Operations', deptMeta.name, `Work Order ${complaint.complaint_id}`]}
    >
      <div className="space-y-6 max-w-7xl mx-auto">
        {/* Navigation & Header Toolbar */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-white/[0.08]">
          <div className="flex items-center gap-3">
            <Link
              to={backUrl}
              className="p-2.5 rounded-xl bg-white/[0.05] hover:bg-white/[0.1] border border-white/[0.08] text-zinc-300 hover:text-white transition-colors flex items-center gap-1.5 text-xs font-semibold"
              title="Return to Assigned Work Orders"
            >
              <ArrowLeft className="w-4 h-4" />
              <span className="hidden sm:inline">Back to Assigned Work</span>
            </Link>
            <div>
              <div className="flex items-center gap-2.5 flex-wrap">
                <span className="text-xl font-bold font-mono tracking-tight text-[#F5F5F5]">
                  {complaint.complaint_id}
                </span>
                <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-[#F36B21]/15 text-[#F36B21] border border-[#F36B21]/30">
                  {deptMeta.code} Work Order
                </span>
                <span className="px-2.5 py-0.5 rounded-full text-[11px] font-mono font-semibold bg-white/[0.08] text-[#F5F5F5] border border-white/[0.08]">
                  Status: {complaint.admin_status || 'In Progress'}
                </span>
                {complaint.escalation_level > 0 && (
                  <span className="flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-red-500/20 text-red-300 border border-red-500/30 animate-pulse">
                    <Flame className="w-3.5 h-3.5 text-red-400" />
                    <span>Tier {complaint.escalation_level} Escalated</span>
                  </span>
                )}
              </div>
              <p className="text-xs text-[#A1A1AA] mt-1 font-medium">
                {deptMeta.name} • Assigned {complaint.assigned_at ? formatToIST(complaint.assigned_at) : 'Active'}
              </p>
            </div>
          </div>

          {/* Quick Department Officer Action Buttons */}
          <div className="flex items-center gap-2 flex-wrap">
            {complaint.admin_status === 'Assigned' && (
              <button
                onClick={handleStartInspection}
                disabled={actionLoading}
                className="px-3.5 py-2 rounded-xl bg-[#F36B21] hover:bg-[#E05A10] text-white text-xs font-semibold flex items-center gap-1.5 shadow-md transition-all cursor-pointer disabled:opacity-50"
              >
                <Wrench className="w-4 h-4" />
                <span>Start Inspection</span>
              </button>
            )}

            <button
              onClick={() => setActiveModal('status')}
              className="px-3.5 py-2 rounded-xl bg-white/[0.08] hover:bg-white/[0.14] border border-white/[0.08] text-[#F5F5F5] text-xs font-semibold flex items-center gap-1.5 transition-all cursor-pointer"
            >
              <RefreshCw className="w-3.5 h-3.5 text-[#F36B21]" />
              <span>Update Progress</span>
            </button>

            <button
              onClick={() => setActiveModal('notes')}
              className="px-3.5 py-2 rounded-xl bg-white/[0.08] hover:bg-white/[0.14] border border-white/[0.08] text-[#F5F5F5] text-xs font-semibold flex items-center gap-1.5 transition-all cursor-pointer"
            >
              <MessageSquare className="w-3.5 h-3.5 text-sky-400" />
              <span>Add Inspection Note</span>
            </button>

            <button
              onClick={() => setActiveModal('evidence')}
              className="px-3.5 py-2 rounded-xl bg-[#102B4E] hover:bg-[#102B4E]/80 border border-white/[0.08] text-white text-xs font-semibold flex items-center gap-1.5 shadow-xs transition-all cursor-pointer"
            >
              <UploadCloud className="w-4 h-4 text-[#F36B21]" />
              <span>Upload Evidence</span>
            </button>

            {!isResolvedOrSubmitted && (
              <button
                onClick={handleOpenResolutionModal}
                className="px-3.5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center gap-1.5 shadow-md transition-all cursor-pointer"
              >
                <CheckCircle2 className="w-4 h-4" />
                <span>Submit Resolution</span>
              </button>
            )}
          </div>
        </div>

        {/* Action Alert Banner */}
        {actionSuccess && (
          <div className="p-3.5 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs flex items-center justify-between shadow-xs">
            <div className="flex items-center gap-2">
              <CheckCircle className="w-4 h-4 flex-shrink-0" />
              <span>{actionSuccess}</span>
            </div>
            <button onClick={() => setActionSuccess(null)} className="text-white/60 hover:text-white cursor-pointer">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* 2-Column Responsive Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main 2-Column Content */}
          <div className="lg:col-span-2 space-y-6">
            {/* Section 1: Complaint & Citizen Description */}
            <div className="p-6 rounded-3xl bg-[#141722]/85 backdrop-blur-xl border border-white/[0.08] shadow-xs">
              <div className="flex items-center justify-between mb-4">
                <span className="text-xs font-bold uppercase tracking-wider text-[#F36B21] flex items-center gap-1.5">
                  <FileText className="w-4 h-4" />
                  Citizen Grievance Information
                </span>
                <span className="text-xs text-[#A1A1AA] font-mono">
                  Reported on {complaint.created_at ? formatToIST(complaint.created_at) : 'N/A'}
                </span>
              </div>

              <h2 className="text-lg font-bold text-[#F5F5F5] mb-2">{complaint.category}</h2>
              <p className="text-xs text-[#A1A1AA] leading-relaxed bg-[#10131C] p-4 rounded-2xl border border-white/[0.08] whitespace-pre-wrap font-sans">
                {complaint.description || 'No detailed citizen description provided.'}
              </p>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-4 pt-4 border-t border-white/[0.08] text-xs">
                <div>
                  <span className="text-[10px] uppercase font-bold text-[#A1A1AA] block">Submission Channel</span>
                  <span className="font-semibold text-[#F5F5F5] capitalize">{complaint.submission_channel || 'Web Portal'}</span>
                </div>
                <div>
                  <span className="text-[10px] uppercase font-bold text-[#A1A1AA] block">Ward / Division</span>
                  <span className="font-semibold text-[#F5F5F5]">Ward {complaint.ward || '12'}</span>
                </div>
                <div>
                  <span className="text-[10px] uppercase font-bold text-[#A1A1AA] block">Verification Status</span>
                  <span className="font-semibold text-emerald-400 capitalize">{complaint.verification_status || 'Verified'}</span>
                </div>
              </div>
            </div>

            {/* Section 2: Location Map & Coordinates */}
            <div className="p-6 rounded-3xl bg-[#141722]/85 backdrop-blur-xl border border-white/[0.08] shadow-xs">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-bold uppercase tracking-wider text-[#F36B21] flex items-center gap-1.5">
                  <MapPin className="w-4 h-4" />
                  Physical Location & Map
                </span>
                {complaint.latitude && complaint.longitude && (
                  <a
                    href={`https://www.google.com/maps?q=${complaint.latitude},${complaint.longitude}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 text-xs text-[#F36B21] hover:underline font-semibold"
                  >
                    <span>Open in Google Maps</span>
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                )}
              </div>

              <div className="text-xs text-[#F5F5F5] mb-3 flex items-center gap-2">
                <span className="font-semibold">{complaint.location_description || 'Coordinates verified on municipal grid'}</span>
                {complaint.latitude && (
                  <span className="font-mono text-[11px] text-[#A1A1AA] bg-[#10131C] px-2 py-0.5 rounded-md border border-white/[0.08]">
                    GPS: {complaint.latitude.toFixed(5)}, {complaint.longitude.toFixed(5)}
                  </span>
                )}
              </div>

              {/* Leaflet Map Preview */}
              {complaint.latitude && complaint.longitude ? (
                <div className="h-64 rounded-2xl overflow-hidden border border-white/[0.08] relative z-0">
                  <MapContainer
                    center={[complaint.latitude, complaint.longitude]}
                    zoom={15}
                    scrollWheelZoom={false}
                    className="h-full w-full"
                  >
                    <TileLayer
                      attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                      url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                    />
                    <Marker position={[complaint.latitude, complaint.longitude]} icon={workOrderMarkerIcon}>
                      <Popup>
                        <div className="text-xs font-sans">
                          <strong>{complaint.complaint_id}</strong>
                          <p>{complaint.category}</p>
                        </div>
                      </Popup>
                    </Marker>
                  </MapContainer>
                </div>
              ) : (
                <div className="h-32 rounded-2xl bg-[#10131C] border border-white/[0.08] flex items-center justify-center text-xs text-[#A1A1AA]">
                  No GPS coordinates recorded for this ticket.
                </div>
              )}
            </div>

            {/* Section 3: Evidence Files & Photographic Proof */}
            <div className="p-6 rounded-3xl bg-[#141722]/85 backdrop-blur-xl border border-white/[0.08] shadow-xs">
              <div className="flex items-center justify-between mb-4">
                <span className="text-xs font-bold uppercase tracking-wider text-[#F36B21] flex items-center gap-1.5">
                  <ImageIcon className="w-4 h-4" />
                  Field & Citizen Evidence ({complaint.evidence?.length || 0})
                </span>
                <button
                  onClick={() => setActiveModal('evidence')}
                  className="inline-flex items-center gap-1.5 text-xs text-[#F36B21] hover:underline font-semibold cursor-pointer"
                >
                  <UploadCloud className="w-3.5 h-3.5" />
                  <span>Upload Inspection Photo</span>
                </button>
              </div>

              {complaint.evidence && complaint.evidence.length > 0 ? (
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  {complaint.evidence.map((ev) => (
                    <div
                      key={ev.id}
                      onClick={() => setSelectedEvidenceView(ev)}
                      className="group relative rounded-2xl overflow-hidden bg-[#10131C] border border-white/[0.08] hover:border-[#F36B21]/50 transition-all cursor-pointer shadow-xs aspect-video flex flex-col justify-end"
                    >
                      <img
                        src={getApiUrl(ev.view_url)}
                        alt={ev.original_filename}
                        className="absolute inset-0 w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                        onError={(e) => {
                          e.target.style.display = 'none'
                        }}
                      />
                      <div className="relative z-10 p-2.5 bg-gradient-to-t from-black/90 via-black/50 to-transparent">
                        <p className="text-[11px] font-semibold text-white truncate">{ev.original_filename}</p>
                        <p className="text-[9px] text-[#A1A1AA] font-mono">
                          {ev.file_size ? `${Math.round(ev.file_size / 1024)} KB` : 'Evidence photo'}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="py-8 rounded-2xl bg-[#10131C] border border-white/[0.08] text-center">
                  <ImageIcon className="w-8 h-8 text-zinc-600 mx-auto mb-2" />
                  <p className="text-xs text-[#A1A1AA]">No citizen or field photographs attached yet.</p>
                  <button
                    onClick={() => setActiveModal('evidence')}
                    className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white/[0.08] hover:bg-white/[0.15] text-xs font-semibold text-[#F5F5F5] cursor-pointer transition-all"
                  >
                    <UploadCloud className="w-3.5 h-3.5" />
                    <span>Upload First Field Photo</span>
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Right Column: Work Assignment, Instructions & Activity Trail */}
          <div className="space-y-6">
            {/* Work Assignment Card */}
            <div className="p-6 rounded-3xl bg-[#141722]/85 backdrop-blur-xl border border-white/[0.08] shadow-xs">
              <span className="text-xs font-bold uppercase tracking-wider text-[#F36B21] flex items-center gap-1.5 mb-4">
                <Building2 className="w-4 h-4" />
                Work Order Assignment
              </span>

              <div className="space-y-3.5 text-xs">
                <div>
                  <span className="text-[10px] uppercase font-bold text-[#A1A1AA] block">Assigned Municipal Division</span>
                  <span className="font-bold text-[#F5F5F5] text-sm">{deptMeta.name}</span>
                </div>

                <div>
                  <span className="text-[10px] uppercase font-bold text-[#A1A1AA] block">Lead Field Officer</span>
                  <div className="flex items-center gap-2 mt-0.5">
                    <div className="w-6 h-6 rounded-lg bg-[#191D2A] border border-white/[0.08] flex items-center justify-center text-[10px] font-bold text-[#F5F5F5]">
                      {complaint.assigned_user?.full_name ? complaint.assigned_user.full_name.charAt(0) : 'E'}
                    </div>
                    <span className="font-semibold text-[#F5F5F5]">
                      {complaint.assigned_user?.full_name || 'Executive Engineer (Division)'}
                    </span>
                  </div>
                </div>

                <div>
                  <span className="text-[10px] uppercase font-bold text-[#A1A1AA] block">Statutory SLA Target</span>
                  <span className="font-semibold text-[#F5F5F5]">
                    {deptMeta.slaDays} Days from Assignment
                  </span>
                </div>

                <div>
                  <span className="text-[10px] uppercase font-bold text-[#A1A1AA] block">Assignment Instructions</span>
                  <div className="mt-1 p-3 rounded-xl bg-[#10131C] border border-white/[0.08] text-[#A1A1AA] italic leading-relaxed text-[11px]">
                    {complaint.assignment_notes || 'Standard division field inspection and repair protocol.'}
                  </div>
                </div>
              </div>
            </div>

            {/* Field Notes & Activity Trail */}
            <div className="p-6 rounded-3xl bg-[#141722]/85 backdrop-blur-xl border border-white/[0.08] shadow-xs">
              <div className="flex items-center justify-between mb-4">
                <span className="text-xs font-bold uppercase tracking-wider text-[#F36B21] flex items-center gap-1.5">
                  <Clock className="w-4 h-4" />
                  Inspection History ({complaint.audit_events?.length || 0})
                </span>
                <button
                  onClick={() => setActiveModal('notes')}
                  className="text-xs text-[#F36B21] hover:underline font-semibold cursor-pointer"
                >
                  + Add Note
                </button>
              </div>

              {complaint.audit_events && complaint.audit_events.length > 0 ? (
                <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
                  {complaint.audit_events.map((ev) => (
                    <div
                      key={ev.id}
                      className="p-3 rounded-2xl bg-[#10131C] border border-white/[0.08] text-xs space-y-1"
                    >
                      <div className="flex items-center justify-between text-[10px] text-[#A1A1AA]">
                        <span className="font-bold text-[#F5F5F5] uppercase tracking-wider">
                          {ev.event_type.replace(/_/g, ' ')}
                        </span>
                        <span className="font-mono">{ev.created_at ? formatToIST(ev.created_at) : ''}</span>
                      </div>
                      <p className="text-[#A1A1AA] leading-snug text-[11px]">
                        {ev.description}
                      </p>
                      {ev.actor_name && (
                        <p className="text-[10px] text-[#A1A1AA]/70 font-mono">
                          Recorded by: {ev.actor_name}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-[#A1A1AA] py-4 text-center">No field notes or activity recorded yet.</p>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* MODAL 1: Update Progress Status */}
      {activeModal === 'status' && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-md flex items-center justify-center p-4 z-50">
          <div className="bg-[#141722] border border-white/[0.08] rounded-3xl p-6 max-w-md w-full shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-[#F5F5F5] flex items-center gap-2">
                <RefreshCw className="w-4 h-4 text-[#F36B21]" />
                <span>Update Work Order Progress</span>
              </h3>
              <button onClick={() => setActiveModal(null)} className="text-[#A1A1AA] hover:text-white cursor-pointer">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wider text-[#A1A1AA] mb-1">
                  Field Progress Status
                </label>
                <select
                  value={targetStatus}
                  onChange={(e) => setTargetStatus(e.target.value)}
                  className="w-full p-2.5 rounded-xl bg-[#10131C] border border-white/[0.08] text-xs text-[#F5F5F5] focus:outline-none focus:border-[#F36B21]"
                >
                  <option value="Under Inspection">Under Inspection (Field team on site)</option>
                  <option value="In Progress">In Progress (Active repair / maintenance)</option>
                  <option value="Resolution Submitted">Resolution Submitted (Repairs done, await officer closure)</option>
                </select>
              </div>

              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wider text-[#A1A1AA] mb-1">
                  Progress / Resolution Details
                </label>
                <textarea
                  rows={3}
                  value={statusNotes}
                  onChange={(e) => setStatusNotes(e.target.value)}
                  placeholder="Detail the physical repair work done, equipment deployed, or findings..."
                  className="w-full p-2.5 rounded-xl bg-[#10131C] border border-white/[0.08] text-xs text-[#F5F5F5] placeholder-[#A1A1AA]/50 focus:outline-none focus:border-[#F36B21]"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setActiveModal(null)}
                className="px-3.5 py-2 rounded-xl bg-white/[0.05] hover:bg-white/[0.1] text-xs font-semibold text-[#A1A1AA] cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => handleUpdateStatus()}
                disabled={actionLoading}
                className="px-4 py-2 rounded-xl bg-[#F36B21] hover:bg-[#E05A10] text-xs font-semibold text-white cursor-pointer disabled:opacity-50"
              >
                {actionLoading ? 'Updating...' : 'Save Work Update'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 2: Add Inspection Note */}
      {activeModal === 'notes' && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-md flex items-center justify-center p-4 z-50">
          <form onSubmit={handleAddInspectionNote} className="bg-[#141722] border border-white/[0.08] rounded-3xl p-6 max-w-md w-full shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-[#F5F5F5] flex items-center gap-2">
                <MessageSquare className="w-4 h-4 text-sky-400" />
                <span>Record Field Inspection Note</span>
              </h3>
              <button type="button" onClick={() => setActiveModal(null)} className="text-[#A1A1AA] hover:text-white cursor-pointer">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-[#A1A1AA] mb-1">
                Inspection Notes & Observations
              </label>
              <textarea
                required
                rows={4}
                value={newInspectionNote}
                onChange={(e) => setNewInspectionNote(e.target.value)}
                placeholder="Enter field engineering observations, measurements, or site condition..."
                className="w-full p-2.5 rounded-xl bg-[#10131C] border border-white/[0.08] text-xs text-[#F5F5F5] placeholder-[#A1A1AA]/50 focus:outline-none focus:border-[#F36B21]"
              />
            </div>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setActiveModal(null)}
                className="px-3.5 py-2 rounded-xl bg-white/[0.05] hover:bg-white/[0.1] text-xs font-semibold text-[#A1A1AA] cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={actionLoading}
                className="px-4 py-2 rounded-xl bg-[#F36B21] hover:bg-[#E05A10] text-xs font-semibold text-white cursor-pointer disabled:opacity-50"
              >
                {actionLoading ? 'Recording...' : 'Add Note to File'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* MODAL 3: Upload Field Evidence */}
      {activeModal === 'evidence' && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-md flex items-center justify-center p-4 z-50">
          <form onSubmit={handleUploadEvidence} className="bg-[#141722] border border-white/[0.08] rounded-3xl p-6 max-w-md w-full shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-[#F5F5F5] flex items-center gap-2">
                <UploadCloud className="w-4 h-4 text-[#F36B21]" />
                <span>Upload Field Inspection Evidence</span>
              </h3>
              <button type="button" onClick={() => setActiveModal(null)} className="text-[#A1A1AA] hover:text-white cursor-pointer">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wider text-[#A1A1AA] mb-1">
                  Inspection Photograph
                </label>
                <input
                  type="file"
                  accept="image/*"
                  required
                  onChange={(e) => setEvidenceFile(e.target.files[0])}
                  className="w-full text-xs text-[#A1A1AA] file:mr-3 file:py-2 file:px-3 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-[#F36B21] file:text-white hover:file:bg-[#E05A10] cursor-pointer"
                />
              </div>

              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wider text-[#A1A1AA] mb-1">
                  Photo Caption / Description (Optional)
                </label>
                <input
                  type="text"
                  value={evidenceCaption}
                  onChange={(e) => setEvidenceCaption(e.target.value)}
                  placeholder="e.g. Completed asphalt patchwork compaction proof"
                  className="w-full p-2.5 rounded-xl bg-[#10131C] border border-white/[0.08] text-xs text-[#F5F5F5] placeholder-[#A1A1AA]/50 focus:outline-none focus:border-[#F36B21]"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setActiveModal(null)}
                className="px-3.5 py-2 rounded-xl bg-white/[0.05] hover:bg-white/[0.1] text-xs font-semibold text-[#A1A1AA] cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={actionLoading}
                className="px-4 py-2 rounded-xl bg-[#F36B21] hover:bg-[#E05A10] text-xs font-semibold text-white cursor-pointer disabled:opacity-50"
              >
                {actionLoading ? 'Uploading...' : 'Upload Evidence'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* MODAL 5: Phase 8 Submit Resolution Dossier */}
      {activeModal === 'submit_resolution' && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-md flex items-center justify-center p-4 z-50">
          <div className="bg-[#141722] border border-white/[0.08] rounded-3xl p-6 max-w-lg w-full shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between pb-3 border-b border-white/[0.08]">
              <h3 className="text-sm font-bold text-[#F5F5F5] flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                <span>Submit Field Resolution Dossier</span>
              </h3>
              <button onClick={() => setActiveModal(null)} className="text-[#A1A1AA] hover:text-white cursor-pointer">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-3 rounded-xl bg-[#102B4E]/60 border border-[#F36B21]/30 text-[11px] text-zinc-300">
              <strong className="text-[#F36B21]">Evidence Verification Protocol:</strong> Submitting completion evidence transitions this grievance to <em>Pending Authority Verification</em>. The Authority Officer must inspect the before/after photos before final closure.
            </div>

            <form onSubmit={handleSubmitResolutionDossier} className="space-y-3.5 text-xs">
              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wider text-[#A1A1AA] mb-1">
                  Work Summary Title
                </label>
                <input
                  type="text"
                  value={resWorkDesc}
                  onChange={(e) => setResWorkDesc(e.target.value)}
                  placeholder="e.g. Resurfaced 12m pothole crater with asphalt mix"
                  className="w-full p-2.5 rounded-xl bg-[#10131C] border border-white/[0.08] text-[#F5F5F5] focus:outline-hidden focus:border-[#F36B21]"
                />
              </div>

              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wider text-[#A1A1AA] mb-1">
                  Specific Repair Action Taken <span className="text-red-400">*</span>
                </label>
                <textarea
                  rows={2}
                  required
                  value={resRepairAction}
                  onChange={(e) => setResRepairAction(e.target.value)}
                  placeholder="Describe the physical work conducted on site, compaction steps, sealant applied..."
                  className="w-full p-2.5 rounded-xl bg-[#10131C] border border-white/[0.08] text-[#F5F5F5] focus:outline-hidden focus:border-[#F36B21]"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-[#A1A1AA] mb-1">
                    Materials / Equipment Used
                  </label>
                  <input
                    type="text"
                    value={resMaterials}
                    onChange={(e) => setResMaterials(e.target.value)}
                    placeholder="e.g. Hot mix bitumen, roller, signage"
                    className="w-full p-2.5 rounded-xl bg-[#10131C] border border-white/[0.08] text-[#F5F5F5] focus:outline-hidden focus:border-[#F36B21]"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-[#A1A1AA] mb-1">
                    After-Repair Evidence Photo URL
                  </label>
                  <input
                    type="text"
                    value={resAfterPhotoUrl}
                    onChange={(e) => setResAfterPhotoUrl(e.target.value)}
                    placeholder="/assets/dept_rpw.jpg or external photo URL"
                    className="w-full p-2.5 rounded-xl bg-[#10131C] border border-white/[0.08] text-[#F5F5F5] focus:outline-hidden focus:border-[#F36B21]"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wider text-[#A1A1AA] mb-1">
                  Field Notes & Site Observations
                </label>
                <textarea
                  rows={2}
                  value={resFieldNotes}
                  onChange={(e) => setResFieldNotes(e.target.value)}
                  placeholder="Site cleared of debris; traffic restored smoothly..."
                  className="w-full p-2.5 rounded-xl bg-[#10131C] border border-white/[0.08] text-[#F5F5F5] focus:outline-hidden focus:border-[#F36B21]"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-white/[0.08]">
                <button
                  type="button"
                  onClick={() => setActiveModal(null)}
                  className="px-3.5 py-2 rounded-xl bg-white/[0.05] hover:bg-white/[0.1] text-xs font-semibold text-[#A1A1AA] cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-xs font-bold text-white cursor-pointer shadow-md disabled:opacity-50 flex items-center gap-2"
                >
                  {actionLoading && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
                  <span>Submit Dossier for Officer Verification</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 4: Evidence Preview Modal */}
      {selectedEvidenceView && (
        <div
          onClick={() => setSelectedEvidenceView(null)}
          className="fixed inset-0 bg-black/85 backdrop-blur-md flex items-center justify-center p-4 z-50 cursor-pointer"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="max-w-3xl w-full bg-[#141722] border border-white/[0.08] rounded-3xl overflow-hidden shadow-2xl"
          >
            <div className="p-4 border-b border-white/[0.08] flex items-center justify-between">
              <div>
                <h4 className="text-xs font-bold text-[#F5F5F5]">{selectedEvidenceView.original_filename}</h4>
                <p className="text-[10px] text-[#A1A1AA] font-mono">
                  Uploaded {selectedEvidenceView.created_at ? formatToIST(selectedEvidenceView.created_at) : ''}
                </p>
              </div>
              <button
                onClick={() => setSelectedEvidenceView(null)}
                className="p-1 rounded-lg bg-white/[0.05] hover:bg-white/[0.1] text-white cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-4 bg-black/50 flex items-center justify-center max-h-[75vh] overflow-hidden">
              <img
                src={`${getApiUrl(selectedEvidenceView.view_url)}${token ? `?token=${encodeURIComponent(token)}` : ''}`}
                alt={selectedEvidenceView.original_filename}
                className="max-h-[70vh] w-auto object-contain rounded-xl"
              />
            </div>
          </div>
        </div>
      )}
    </AuthorityLayout>
  )
}

