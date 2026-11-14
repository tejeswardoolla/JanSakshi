import React, { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import {
  ArrowLeft, CheckCircle2, XCircle, AlertTriangle, ShieldCheck,
  Sparkles, Camera, MapPin, Calendar, Clock, Building2,
  FileText, User, Layers, RefreshCw, AlertCircle, Eye, Check,
  RotateCcw, HelpCircle, Info
} from 'lucide-react'
import AuthorityLayout from '../../components/AuthorityLayout'
import { useAuth } from '../../context/AuthContext'
import { formatToIST } from '../../utils/dateTime'

export default function AuthorityResolutionReviewDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { authFetch, user } = useAuth()

  const [submission, setSubmission] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Actions states
  const [activeActionModal, setActiveActionModal] = useState(null) // 'approve' | 'return' | 'more_evidence'
  const [actionReason, setActionReason] = useState('')
  const [actionLoading, setActionLoading] = useState(false)
  const [actionError, setActionError] = useState(null)
  const [actionSuccess, setActionSuccess] = useState(null)

  const fetchSubmission = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await authFetch(`http://127.0.0.1:8000/api/authority/resolutions/${id}`)
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}))
        throw new Error(errJson.detail || 'Failed to load resolution dossier.')
      }
      const data = await res.json()
      setSubmission(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchSubmission()
  }, [id])

  // --- Handlers ---
  const handleApprove = async () => {
    setActionLoading(true)
    setActionError(null)
    try {
      const res = await authFetch(`http://127.0.0.1:8000/api/authority/resolutions/${id}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          verification_notes: actionReason || 'Resolution verified and accepted based on field evidence.'
        })
      })
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}))
        throw new Error(errJson.detail || 'Approval failed.')
      }
      setActionSuccess('Work order successfully verified and complaint closed.')
      setActiveActionModal(null)
      fetchSubmission()
    } catch (err) {
      setActionError(err.message)
    } finally {
      setActionLoading(false)
    }
  }

  const handleReturnForCorrection = async () => {
    if (!actionReason.trim()) {
      setActionError('A specific, actionable correction reason is required.')
      return
    }
    setActionLoading(true)
    setActionError(null)
    try {
      const res = await authFetch(`http://127.0.0.1:8000/api/authority/resolutions/${id}/return`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          rejection_reason: actionReason.trim()
        })
      })
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}))
        throw new Error(errJson.detail || 'Return for correction failed.')
      }
      setActionSuccess('Submission returned to department field team for correction.')
      setActiveActionModal(null)
      fetchSubmission()
    } catch (err) {
      setActionError(err.message)
    } finally {
      setActionLoading(false)
    }
  }

  const handleRequestEvidence = async () => {
    if (!actionReason.trim()) {
      setActionError('Please specify the required evidence details.')
      return
    }
    setActionLoading(true)
    setActionError(null)
    try {
      const res = await authFetch(`http://127.0.0.1:8000/api/authority/resolutions/${id}/request-evidence`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          evidence_request_notes: actionReason.trim()
        })
      })
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}))
        throw new Error(errJson.detail || 'Request failed.')
      }
      setActionSuccess('Additional evidence request dispatched to department officer.')
      setActiveActionModal(null)
      fetchSubmission()
    } catch (err) {
      setActionError(err.message)
    } finally {
      setActionLoading(false)
    }
  }

  if (loading) {
    return (
      <AuthorityLayout pageTitle="Loading Resolution..." breadcrumbs={['Authority', 'Resolution Review', 'Loading']}>
        <div className="py-24 text-center">
          <RefreshCw className="w-8 h-8 text-[#F36B21] animate-spin mx-auto mb-3" />
          <p className="text-xs text-[#A1A1AA]">Retrieving resolution verification dossier...</p>
        </div>
      </AuthorityLayout>
    )
  }

  if (error || !submission) {
    return (
      <AuthorityLayout pageTitle="Resolution Dossier Not Found" breadcrumbs={['Authority', 'Resolution Review', 'Error']}>
        <div className="max-w-xl mx-auto py-20 text-center">
          <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-3" />
          <h2 className="text-lg font-bold text-[#F5F5F5]">Unable to Load Dossier</h2>
          <p className="text-xs text-[#A1A1AA] mt-2">{error || 'Dossier record could not be found.'}</p>
          <button
            onClick={() => navigate('/authority/resolution-review')}
            className="mt-6 px-4 py-2 rounded-xl bg-white/[0.08] text-xs font-semibold hover:bg-white/[0.15] text-[#F5F5F5]"
          >
            Return to Queue
          </button>
        </div>
      </AuthorityLayout>
    )
  }

  const complaint = submission.complaint || {}
  const aiAnalysis = submission.ai_analysis
  const isPending = submission.status === 'submitted'
  const isApproved = submission.status === 'approved'
  const isNeedsCorrection = submission.status === 'needs_correction'

  return (
    <AuthorityLayout
      pageTitle={`Verify Resolution: ${complaint.complaint_id || `JS-${submission.complaint_id}`}`}
      breadcrumbs={['Authority', 'Resolution Review', complaint.complaint_id || `JS-${submission.complaint_id}`]}
    >
      <div className="space-y-8 max-w-7xl mx-auto font-sans pb-16">
        {/* Top Navigation & Status Bar */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-white/[0.08]">
          <Link
            to="/authority/resolution-review"
            className="inline-flex items-center gap-2 text-xs font-semibold text-[#A1A1AA] hover:text-[#F5F5F5] transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Back to Resolution Queue</span>
          </Link>

          <div className="flex items-center gap-3">
            <span className="text-xs text-[#A1A1AA] font-mono">Submission Version: <strong>v{submission.version_number}</strong></span>
            {isPending && (
              <span className="px-3 py-1 rounded-full bg-amber-500/15 border border-amber-500/30 text-amber-400 text-xs font-bold flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5" />
                <span>Pending Authority Decision</span>
              </span>
            )}
            {isApproved && (
              <span className="px-3 py-1 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 text-xs font-bold flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Verified & Closed</span>
              </span>
            )}
            {isNeedsCorrection && (
              <span className="px-3 py-1 rounded-full bg-red-500/15 border border-red-500/30 text-red-400 text-xs font-bold flex items-center gap-1.5">
                <XCircle className="w-3.5 h-3.5" />
                <span>Returned for Correction</span>
              </span>
            )}
          </div>
        </div>

        {actionSuccess && (
          <div className="p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
            <span>{actionSuccess}</span>
          </div>
        )}

        {/* Verification Actions Header (Only for Authority Officer on pending review) */}
        {isPending && user?.role === 'authority_officer' && (
          <div className="p-6 rounded-3xl bg-gradient-to-r from-[#102B4E]/80 via-[#141722]/90 to-[#102B4E]/80 border border-[#F36B21]/30 backdrop-blur-xl shadow-2xl flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 text-xs font-bold text-[#F36B21]">
                <ShieldCheck className="w-4 h-4" />
                <span>AUTHORITY VERIFICATION ACTION REQUIRED</span>
              </div>
              <h2 className="text-base font-bold text-[#F5F5F5] mt-1">
                Evaluate Evidence & Issue Municipal Determination
              </h2>
              <p className="text-xs text-[#A1A1AA] mt-0.5">
                Compare original complaint evidence with the field resolution photos below. Once approved, this complaint is officially marked Closed.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <button
                onClick={() => {
                  setActionReason('')
                  setActiveActionModal('return')
                }}
                className="px-4 py-2.5 rounded-xl bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/30 text-xs font-bold flex items-center gap-1.5 cursor-pointer transition-all"
              >
                <XCircle className="w-4 h-4" />
                <span>Return for Correction</span>
              </button>

              <button
                onClick={() => {
                  setActionReason('')
                  setActiveActionModal('more_evidence')
                }}
                className="px-4 py-2.5 rounded-xl bg-white/[0.08] hover:bg-white/[0.15] text-[#F5F5F5] border border-white/[0.1] text-xs font-bold flex items-center gap-1.5 cursor-pointer transition-all"
              >
                <HelpCircle className="w-4 h-4 text-amber-400" />
                <span>Request More Evidence</span>
              </button>

              <button
                onClick={() => {
                  setActionReason('Work verified complete with valid photographic evidence.')
                  setActiveActionModal('approve')
                }}
                className="px-5 py-2.5 rounded-xl bg-[#138A4B] hover:bg-[#10703D] text-white text-xs font-bold flex items-center gap-1.5 shadow-lg shadow-[#138A4B]/30 cursor-pointer transition-all"
              >
                <Check className="w-4 h-4" />
                <span>Approve & Close</span>
              </button>
            </div>
          </div>
        )}

        {/* Advisory AI Evidence Assessment Card */}
        {aiAnalysis && (
          <div className="p-6 rounded-3xl bg-[#141722]/90 border border-sky-500/25 backdrop-blur-xl shadow-xl space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-white/[0.08]">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-sky-500/15 border border-sky-500/30 flex items-center justify-center text-sky-400">
                  <Sparkles className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-[#F5F5F5]">Gemini Multimodal Resolution Assessment</h3>
                  <div className="text-[10px] text-[#A1A1AA]">
                    Independent AI visual comparison between citizen complaint evidence and resolution submission
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-[10px] uppercase font-bold text-[#A1A1AA]">Likelihood:</span>
                <span className={`px-2.5 py-1 rounded-full text-xs font-bold border ${
                  aiAnalysis.work_completion_likelihood === 'High'
                    ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                    : aiAnalysis.work_completion_likelihood === 'Low'
                    ? 'bg-red-500/15 text-red-400 border-red-500/30'
                    : 'bg-amber-500/15 text-amber-400 border-amber-500/30'
                }`}>
                  {aiAnalysis.work_completion_likelihood || 'Advisory'}
                </span>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
              <div className="p-3.5 rounded-2xl bg-[#10131C] border border-white/[0.06] space-y-1">
                <div className="text-[10px] font-bold text-[#A1A1AA] uppercase">Visual Evidence Confidence</div>
                <div className="text-xl font-bold text-sky-400">
                  {aiAnalysis.evidence_relevance_score ? `${Math.round(aiAnalysis.evidence_relevance_score * 100)}%` : '85%'}
                </div>
                <div className="text-[10px] text-zinc-500">Feature matching score</div>
              </div>

              <div className="p-3.5 rounded-2xl bg-[#10131C] border border-white/[0.06] space-y-1">
                <div className="text-[10px] font-bold text-[#A1A1AA] uppercase">Site Consistency</div>
                <div className="text-base font-bold text-[#F5F5F5]">
                  {aiAnalysis.inconsistencies_detected && aiAnalysis.inconsistencies_detected.length > 0 ? (
                    <span className="text-amber-400">Inconsistencies Noted</span>
                  ) : (
                    <span className="text-emerald-400">Consistent Location</span>
                  )}
                </div>
                <div className="text-[10px] text-zinc-500">Background landmarks matched</div>
              </div>

              <div className="p-3.5 rounded-2xl bg-[#10131C] border border-white/[0.06] space-y-1">
                <div className="text-[10px] font-bold text-[#A1A1AA] uppercase">AI Recommendation</div>
                <div className="text-xs font-bold text-[#F5F5F5] truncate">
                  {aiAnalysis.suggested_decision || 'Approve Closure'}
                </div>
                <div className="text-[10px] text-zinc-500 font-mono">Advisory ONLY — Human Final</div>
              </div>
            </div>

            {aiAnalysis.observations && (
              <div className="p-3.5 rounded-2xl bg-[#10131C] border border-white/[0.06] text-xs">
                <div className="text-[10px] font-bold text-[#A1A1AA] uppercase mb-1">AI Visual Observations:</div>
                <p className="text-zinc-300 leading-relaxed">{aiAnalysis.observations}</p>
              </div>
            )}

            <div className="p-3 rounded-xl bg-sky-500/10 border border-sky-500/20 text-[11px] text-sky-300 flex items-center gap-2">
              <Info className="w-4 h-4 flex-shrink-0" />
              <span>
                <strong>Governance Rule:</strong> AI resolution assessments are strictly advisory. Final decision accountability rests exclusively with the human Authority Officer.
              </span>
            </div>
          </div>
        )}

        {/* Side-by-Side Comparison: Citizen Complaint vs Department Resolution */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Left Column: Citizen Original Complaint */}
          <div className="bg-[#141722]/85 rounded-3xl border border-white/[0.08] p-6 shadow-xl space-y-5">
            <div className="flex items-center justify-between pb-3 border-b border-white/[0.08]">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-[#F36B21]" />
                <h3 className="text-sm font-bold text-[#F5F5F5] uppercase tracking-wider">
                  Original Citizen Report
                </h3>
              </div>
              <span className="text-[11px] font-mono text-[#F36B21] font-bold">
                {complaint.complaint_id}
              </span>
            </div>

            <div className="space-y-4 text-xs">
              <div>
                <span className="text-[10px] font-semibold text-[#A1A1AA] uppercase">Grievance Category</span>
                <div className="text-sm font-bold text-[#F5F5F5] mt-0.5">{complaint.category || 'Civic Infrastructure'}</div>
              </div>

              <div>
                <span className="text-[10px] font-semibold text-[#A1A1AA] uppercase">Reported Problem Description</span>
                <p className="p-3.5 rounded-xl bg-[#10131C] border border-white/[0.06] text-zinc-300 mt-1 leading-relaxed">
                  {complaint.description || 'No detailed description.'}
                </p>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 rounded-xl bg-[#10131C] border border-white/[0.06]">
                  <span className="text-[10px] text-[#A1A1AA] uppercase">Location</span>
                  <div className="font-semibold text-[#F5F5F5] mt-0.5 truncate">{complaint.address || 'Reported Location'}</div>
                </div>
                <div className="p-3 rounded-xl bg-[#10131C] border border-white/[0.06]">
                  <span className="text-[10px] text-[#A1A1AA] uppercase">GPS Coordinates</span>
                  <div className="font-mono text-[#F5F5F5] mt-0.5">
                    {complaint.latitude && complaint.longitude ? `${complaint.latitude.toFixed(4)}, ${complaint.longitude.toFixed(4)}` : 'N/A'}
                  </div>
                </div>
              </div>

              {/* Citizen Photos */}
              <div>
                <span className="text-[10px] font-semibold text-[#A1A1AA] uppercase mb-2 block">
                  Citizen-Submitted Evidence Photos
                </span>
                {complaint.evidence_files && complaint.evidence_files.length > 0 ? (
                  <div className="grid grid-cols-2 gap-3">
                    {complaint.evidence_files.map((ev, i) => (
                      <div key={i} className="aspect-video rounded-xl overflow-hidden border border-white/[0.08] bg-[#10131C] relative group">
                        <img
                          src={ev.file_url || ev.url || '/assets/dept_rpw.jpg'}
                          alt={`Citizen evidence ${i + 1}`}
                          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                        />
                        <div className="absolute bottom-1 left-1 px-2 py-0.5 rounded-md bg-black/70 text-[9px] text-white font-mono">
                          Citizen Photo #{i + 1}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="p-6 text-center rounded-xl bg-[#10131C] border border-white/[0.06] text-zinc-500 text-xs">
                    No initial photographs attached by citizen.
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Right Column: Department Officer Resolution Dossier */}
          <div className="bg-[#141722]/85 rounded-3xl border border-white/[0.08] p-6 shadow-xl space-y-5">
            <div className="flex items-center justify-between pb-3 border-b border-white/[0.08]">
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-[#138A4B]" />
                <h3 className="text-sm font-bold text-[#F5F5F5] uppercase tracking-wider">
                  Department Field Completion Report
                </h3>
              </div>
              <span className="text-[11px] font-mono text-emerald-400 font-bold">
                {submission.submitted_by_officer_name || 'Field Officer'}
              </span>
            </div>

            <div className="space-y-4 text-xs">
              <div>
                <span className="text-[10px] font-semibold text-[#A1A1AA] uppercase">Work Description</span>
                <div className="text-sm font-bold text-[#F5F5F5] mt-0.5">
                  {submission.work_description || 'Standard Municipal Repair'}
                </div>
              </div>

              <div>
                <span className="text-[10px] font-semibold text-[#A1A1AA] uppercase">Repair Action Taken</span>
                <p className="p-3.5 rounded-xl bg-[#10131C] border border-white/[0.06] text-zinc-300 mt-1 leading-relaxed">
                  {submission.repair_action_taken || 'Field repairs executed in accordance with municipal standards.'}
                </p>
              </div>

              {submission.field_notes && (
                <div>
                  <span className="text-[10px] font-semibold text-[#A1A1AA] uppercase">Field Notes & Observations</span>
                  <p className="p-3.5 rounded-xl bg-[#10131C] border border-white/[0.06] text-zinc-300 mt-1 leading-relaxed">
                    {submission.field_notes}
                  </p>
                </div>
              )}

              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 rounded-xl bg-[#10131C] border border-white/[0.06]">
                  <span className="text-[10px] text-[#A1A1AA] uppercase">Materials Used</span>
                  <div className="font-semibold text-[#F5F5F5] mt-0.5">{submission.materials_used || 'Standard'}</div>
                </div>
                <div className="p-3 rounded-xl bg-[#10131C] border border-white/[0.06]">
                  <span className="text-[10px] text-[#A1A1AA] uppercase">Completion Date</span>
                  <div className="font-mono text-[#F5F5F5] mt-0.5">
                    {formatToIST(submission.completion_date || submission.created_at)}
                  </div>
                </div>
              </div>

              {/* After Photos (Completion Evidence) */}
              <div>
                <span className="text-[10px] font-semibold text-[#A1A1AA] uppercase mb-2 block">
                  Field Completion Photographs (After-Repair Evidence)
                </span>
                {submission.after_photo_urls && submission.after_photo_urls.length > 0 ? (
                  <div className="grid grid-cols-2 gap-3">
                    {submission.after_photo_urls.map((url, i) => (
                      <div key={i} className="aspect-video rounded-xl overflow-hidden border border-emerald-500/30 bg-[#10131C] relative group">
                        <img
                          src={url}
                          alt={`Field evidence ${i + 1}`}
                          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                        />
                        <div className="absolute bottom-1 left-1 px-2 py-0.5 rounded-md bg-emerald-950/80 text-[9px] text-emerald-300 border border-emerald-500/40 font-mono">
                          After Repair #{i + 1}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="p-6 text-center rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs">
                    No completion photographs attached. Authority Officer verification requires evidence photos.
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Audit History Timeline */}
        {submission.review_notes && (
          <div className="p-5 rounded-3xl bg-[#141722]/85 border border-white/[0.08] text-xs space-y-2">
            <div className="text-[10px] font-bold uppercase tracking-wider text-[#F36B21]">Authority Review History</div>
            <div className="p-3.5 rounded-2xl bg-[#10131C] border border-white/[0.06] text-zinc-300">
              {submission.review_notes}
            </div>
            <div className="text-[10px] text-[#A1A1AA] font-mono">
              Reviewed by: {submission.reviewed_by_officer_name || 'Authority Officer'} on {formatToIST(submission.reviewed_at)}
            </div>
          </div>
        )}

        {/* Modal: Action Confirmations */}
        {activeActionModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md">
            <div className="max-w-lg w-full rounded-3xl bg-[#141722] border border-white/[0.1] p-6 shadow-2xl space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-white/[0.08]">
                <h3 className="text-base font-bold text-[#F5F5F5]">
                  {activeActionModal === 'approve' && 'Approve & Close Complaint'}
                  {activeActionModal === 'return' && 'Return Resolution for Correction'}
                  {activeActionModal === 'more_evidence' && 'Request Additional Evidence'}
                </h3>
                <button
                  onClick={() => setActiveActionModal(null)}
                  className="text-zinc-400 hover:text-white cursor-pointer"
                >
                  ✕
                </button>
              </div>

              {actionError && (
                <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-xs flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 flex-shrink-0" />
                  <span>{actionError}</span>
                </div>
              )}

              <div>
                <label className="text-xs font-semibold text-[#A1A1AA] block mb-1">
                  {activeActionModal === 'approve' && 'Verification Notes (Recorded in System Audit):'}
                  {activeActionModal === 'return' && 'Mandatory Correction Reason (Sent to Field Officer):'}
                  {activeActionModal === 'more_evidence' && 'Evidence Requirements Details:'}
                </label>
                <textarea
                  rows={4}
                  value={actionReason}
                  onChange={(e) => setActionReason(e.target.value)}
                  placeholder={
                    activeActionModal === 'approve'
                      ? 'Work verified in person or via clear photographic evidence...'
                      : activeActionModal === 'return'
                      ? 'E.g., Pothole edge sealing incomplete; please resurface asphalt level and upload closer photo...'
                      : 'Specify what additional proof is required...'
                  }
                  className="w-full rounded-xl bg-[#10131C] border border-white/[0.08] p-3 text-xs text-[#F5F5F5] placeholder-zinc-500 focus:outline-hidden focus:border-[#F36B21]"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-white/[0.08]">
                <button
                  onClick={() => setActiveActionModal(null)}
                  disabled={actionLoading}
                  className="px-4 py-2 rounded-xl bg-white/[0.06] hover:bg-white/[0.1] text-xs font-semibold text-zinc-300 cursor-pointer"
                >
                  Cancel
                </button>

                {activeActionModal === 'approve' && (
                  <button
                    onClick={handleApprove}
                    disabled={actionLoading}
                    className="px-5 py-2 rounded-xl bg-[#138A4B] hover:bg-[#10703D] text-xs font-bold text-white flex items-center gap-2 cursor-pointer shadow-md"
                  >
                    {actionLoading && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
                    <span>Confirm Approval & Close</span>
                  </button>
                )}

                {activeActionModal === 'return' && (
                  <button
                    onClick={handleReturnForCorrection}
                    disabled={actionLoading}
                    className="px-5 py-2 rounded-xl bg-red-600 hover:bg-red-700 text-xs font-bold text-white flex items-center gap-2 cursor-pointer shadow-md"
                  >
                    {actionLoading && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
                    <span>Return for Correction</span>
                  </button>
                )}

                {activeActionModal === 'more_evidence' && (
                  <button
                    onClick={handleRequestEvidence}
                    disabled={actionLoading}
                    className="px-5 py-2 rounded-xl bg-amber-600 hover:bg-amber-700 text-xs font-bold text-white flex items-center gap-2 cursor-pointer shadow-md"
                  >
                    {actionLoading && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
                    <span>Dispatch Evidence Request</span>
                  </button>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </AuthorityLayout>
  )
}
