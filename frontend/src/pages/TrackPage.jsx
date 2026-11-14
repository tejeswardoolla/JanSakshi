import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ArrowLeft, Search, ShieldCheck, MapPin, Clock, Tag, ExternalLink, AlertCircle, Loader2, Layers, CheckCircle2 } from 'lucide-react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import { formatToIST } from '../utils/dateTime'

export default function TrackPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const initialId = searchParams.get('id') || ''

  const [complaintId, setComplaintId] = useState(initialId)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [record, setRecord] = useState(null)

  const handleTrack = async (idToQuery) => {
    const targetId = (idToQuery || complaintId).trim()
    if (!targetId) return

    setLoading(true)
    setError(null)
    setRecord(null)

    try {
      const res = await fetch(`/api/complaints/${encodeURIComponent(targetId)}`)
      const data = await res.json()
      if (res.ok) {
        setRecord(data)
      } else {
        setError(data.detail || 'Could not find a complaint matching that identifier.')
      }
    } catch (err) {
      setError('Unable to reach the tracking service. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (initialId) {
      handleTrack(initialId)
    }
  }, [initialId])

  return (
    <div className="min-h-screen bg-[#08090B] flex flex-col selection:bg-[#F36B21] selection:text-white">
      <Navbar />

      <main className="flex-1 max-w-4xl mx-auto w-full px-6 pt-32 pb-24">
        {/* Navigation Breadcrumb */}
        <button
          onClick={() => navigate('/')}
          className="flex items-center gap-2 text-white/40 hover:text-white text-xs mb-8 transition-colors group"
        >
          <ArrowLeft size={14} className="group-hover:-translate-x-1 transition-transform" />
          <span>Back to Home</span>
        </button>

        {/* Page Header */}
        <div className="mb-10 text-center sm:text-left">
          <span className="text-[#F36B21] text-xs font-bold tracking-widest uppercase">
            Civic Transparency & Accountability
          </span>
          <h1 className="text-3xl sm:text-4xl font-extrabold text-white mt-2">
            Track Incident Resolution
          </h1>
          <p className="text-white/50 text-sm mt-2 max-w-xl">
            Enter your official JanSakshi Complaint ID to verify the live status of your public infrastructure report.
          </p>
        </div>

        {/* Search Bar */}
        <div className="bg-[#121316] border border-white/10 rounded-2xl p-3 sm:p-4 mb-8 shadow-xl">
          <form
            onSubmit={(e) => {
              e.preventDefault()
              handleTrack()
            }}
            className="flex flex-col sm:flex-row gap-3"
          >
            <div className="relative flex-1">
              <input
                type="text"
                value={complaintId}
                onChange={(e) => setComplaintId(e.target.value)}
                placeholder="Enter Complaint ID (e.g., JS-2026-00001)"
                className="w-full bg-[#08090B] border border-white/15 rounded-xl px-4 py-3 text-sm text-white font-mono placeholder-white/30 focus:outline-none focus:border-[#F36B21] transition-colors"
              />
            </div>
            <button
              type="submit"
              disabled={loading || !complaintId.trim()}
              className="flex items-center justify-center gap-2 bg-[#F36B21] hover:bg-[#F36B21]/90 text-white font-semibold text-xs sm:text-sm px-6 py-3 rounded-xl transition-all shadow-md shadow-[#F36B21]/20 disabled:opacity-50"
            >
              {loading ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />}
              <span>Track Status</span>
            </button>
          </form>

          {/* Privacy Note */}
          <p className="text-[11px] text-white/30 mt-2 px-1">
            Privacy Protected: Citizen contact details and identity are strictly safeguarded and hidden from public lookup.
          </p>
        </div>

        {/* Error State */}
        <AnimatePresence>
          {error && (
            <motion.div
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="flex items-center gap-3 bg-rose-500/10 border border-rose-500/20 text-rose-300 p-4 rounded-2xl mb-8 text-sm"
            >
              <AlertCircle size={18} className="flex-shrink-0" />
              <span>{error}</span>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Loaded Record Details */}
        <AnimatePresence>
          {record && (
            <motion.div
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              className="bg-[#121316] border border-white/10 rounded-3xl p-6 sm:p-8 space-y-6 shadow-2xl"
            >
              {/* Status Header */}
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-white/10 pb-6">
                <div>
                  <span className="text-[10px] uppercase font-bold tracking-wider text-white/40">
                    Official Reference
                  </span>
                  <h3 className="font-mono text-2xl font-black text-[#F36B21]">
                    {record.complaint_id}
                  </h3>
                </div>

                <div className="flex items-center gap-2">
                  <span className={`px-3.5 py-1.5 rounded-full text-xs font-bold uppercase tracking-wider border flex items-center gap-2 ${
                    record.status === 'Closed' || record.status === 'Resolved'
                      ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                      : record.status === 'Resolution Submitted' || record.admin_status === 'Pending Authority Verification'
                      ? 'bg-sky-500/15 text-sky-300 border-sky-500/30'
                      : record.status === 'In Progress'
                      ? 'bg-amber-500/15 text-amber-300 border-amber-500/30'
                      : 'bg-[#F36B21]/15 text-[#F36B21] border-[#F36B21]/30'
                  }`}>
                    <span className="w-2 h-2 rounded-full bg-current animate-pulse" />
                    <span>
                      {record.status === 'Closed' || record.status === 'Resolved'
                        ? 'Resolved & Closed'
                        : record.status === 'Resolution Submitted' || record.admin_status === 'Pending Authority Verification'
                        ? 'Resolution Submitted (Awaiting Authority Verification)'
                        : record.status}
                    </span>
                  </span>
                </div>
              </div>

              {/* Citizen Workflow Progress Bar */}
              <div className="bg-white/[0.02] border border-white/5 p-4 rounded-2xl">
                <div className="text-[10px] font-bold uppercase tracking-wider text-white/40 mb-3">
                  Resolution Progress Tracking
                </div>
                <div className="grid grid-cols-4 gap-2 text-center text-[11px]">
                  <div className={`p-2 rounded-xl border ${
                    ['Received', 'Assigned', 'In Progress', 'Resolution Submitted', 'Closed', 'Resolved'].includes(record.status) || true
                      ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300 font-bold'
                      : 'bg-white/[0.02] border-white/5 text-white/40'
                  }`}>
                    1. Intake
                  </div>
                  <div className={`p-2 rounded-xl border ${
                    ['Assigned', 'In Progress', 'Resolution Submitted', 'Closed', 'Resolved'].includes(record.status)
                      ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300 font-bold'
                      : 'bg-white/[0.02] border-white/5 text-white/40'
                  }`}>
                    2. Assigned
                  </div>
                  <div className={`p-2 rounded-xl border ${
                    ['In Progress', 'Resolution Submitted', 'Closed', 'Resolved'].includes(record.status)
                      ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300 font-bold'
                      : 'bg-white/[0.02] border-white/5 text-white/40'
                  }`}>
                    3. In Progress
                  </div>
                  <div className={`p-2 rounded-xl border ${
                    ['Closed', 'Resolved'].includes(record.status)
                      ? 'bg-emerald-500/15 border-emerald-500/40 text-emerald-300 font-bold'
                      : record.status === 'Resolution Submitted'
                      ? 'bg-sky-500/15 border-sky-500/40 text-sky-300 font-bold animate-pulse'
                      : 'bg-white/[0.02] border-white/5 text-white/40'
                  }`}>
                    {['Closed', 'Resolved'].includes(record.status) ? '4. Verified Closed' : '4. Verification'}
                  </div>
                </div>
              </div>

              {/* Data Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                <div className="bg-white/[0.02] border border-white/5 p-4 rounded-xl space-y-1">
                  <span className="text-white/40 flex items-center gap-1.5">
                    <Tag size={13} className="text-[#F36B21]" /> Category
                  </span>
                  <p className="text-white font-semibold text-sm">{record.category}</p>
                </div>

                <div className="bg-white/[0.02] border border-white/5 p-4 rounded-xl space-y-1">
                  <span className="text-white/40 flex items-center gap-1.5">
                    <Clock size={13} className="text-[#138A4B]" /> Timestamp
                  </span>
                  <p className="text-white font-medium">
                    {formatToIST(record.created_at)}
                  </p>
                </div>

                <div className="bg-white/[0.02] border border-white/5 p-4 rounded-xl space-y-2 sm:col-span-2">
                  <span className="text-white/40 flex items-center gap-1.5">
                    <MapPin size={13} className="text-[#3B82F6]" /> Incident Location
                  </span>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-white/70 font-mono">
                      {record.latitude}, {record.longitude} (Source: {record.location_source})
                    </span>
                    {record.google_maps_url && (
                      <a
                        href={record.google_maps_url}
                        target="_blank"
                        rel="noreferrer"
                        className="flex items-center gap-1 text-[#F36B21] hover:underline font-medium"
                      >
                        <span>Open Location in Google Maps</span>
                        <ExternalLink size={12} />
                      </a>
                    )}
                  </div>
                </div>

                <div className="bg-white/[0.02] border border-white/5 p-4 rounded-xl space-y-1 sm:col-span-2">
                  <span className="text-white/40">Reported Problem Description</span>
                  <p className="text-white/80 text-sm leading-relaxed whitespace-pre-wrap pt-1">
                    {record.description}
                  </p>
                </div>
              </div>

              {/* Evidence count summary */}
              <div className="bg-white/[0.02] border border-white/5 p-4 rounded-xl flex items-center justify-between text-xs">
                <span className="text-white/50">Attached Photographic / Video Evidence:</span>
                <span className="text-white font-semibold">{record.evidence_count} file(s) registered</span>
              </div>

              {/* AI Verification Assessment Card (Phase 4) */}
              {record.latest_ai_analysis && (
                <div className="border border-white/10 rounded-2xl p-5 bg-[#0A0B0D] space-y-4">
                  <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 border-b border-white/5 pb-3">
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 rounded-full bg-[#F36B21] dot-blink" />
                      <span className="text-xs font-bold text-white uppercase tracking-wider">
                        AI Assessment · Not Final Verification
                      </span>
                    </div>
                    <span className="text-[11px] text-white/40">
                      Model: {record.latest_ai_analysis.model_name || 'Gemini Multimodal'}
                    </span>
                  </div>

                  {record.latest_ai_analysis.analysis_status === 'completed' ? (
                    <div className="space-y-3 text-xs">
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                        <div className="bg-white/[0.03] p-3 rounded-xl border border-white/5">
                          <span className="text-white/40 block text-[10px] uppercase">Recommended Category</span>
                          <span className="text-white font-semibold">{record.latest_ai_analysis.predicted_category || 'N/A'}</span>
                          {record.latest_ai_analysis.category_confidence && (
                            <span className="text-white/30 text-[10px] block mt-0.5">
                              Confidence: {Math.round(record.latest_ai_analysis.category_confidence * 100)}%
                            </span>
                          )}
                        </div>
                        <div className="bg-white/[0.03] p-3 rounded-xl border border-white/5">
                          <span className="text-white/40 block text-[10px] uppercase">Evidence Relevance</span>
                          <span className="text-emerald-400 font-semibold capitalize">
                            {record.latest_ai_analysis.evidence_relevance?.replace('_', ' ')}
                          </span>
                          {record.latest_ai_analysis.relevance_score !== null && (
                            <span className="text-white/30 text-[10px] block mt-0.5">
                              Relevance: {record.latest_ai_analysis.relevance_score}/100
                            </span>
                          )}
                        </div>
                        <div className="bg-white/[0.03] p-3 rounded-xl border border-white/5">
                          <span className="text-white/40 block text-[10px] uppercase">Recommended Severity</span>
                          <span className="text-[#F36B21] font-bold uppercase">
                            {record.latest_ai_analysis.recommended_severity || 'Medium'}
                          </span>
                        </div>
                      </div>

                      {record.latest_ai_analysis.reasoning && (
                        <p className="text-white/70 text-xs leading-relaxed bg-white/[0.02] p-3 rounded-xl border border-white/5">
                          <strong className="text-white/90">Observation: </strong>
                          {record.latest_ai_analysis.reasoning}
                        </p>
                      )}

                      <div className="flex items-center gap-2 pt-1 text-[11px] text-amber-300/80">
                        <ShieldCheck size={14} className="text-amber-400 flex-shrink-0" />
                        <span>Human Review Flagged: Official municipal verification required prior to dispatch.</span>
                      </div>
                    </div>
                  ) : record.latest_ai_analysis.analysis_status === 'not_configured' ? (
                    <div className="text-xs text-white/50 space-y-1">
                      <p className="text-white/80 font-medium">Gemini AI Engine Standby</p>
                      <p className="text-white/40 text-[11px]">
                        AI analysis is awaiting Google Gemini API credentials. Normal complaint registration and municipal routing remain fully operational.
                      </p>
                    </div>
                  ) : (
                    <div className="text-xs text-white/40">
                      <span>Status: {record.latest_ai_analysis.analysis_status}</span>
                    </div>
                  )}
                </div>
              )}

              {/* Physical Issue & Correlation Status (Phase 5) */}
              {record.associated_issue ? (
                <div className="border border-emerald-500/20 bg-emerald-500/[0.04] rounded-2xl p-5 space-y-3">
                  <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 border-b border-emerald-500/10 pb-3">
                    <div className="flex items-center gap-2">
                      <Layers size={16} className="text-emerald-400" />
                      <span className="text-xs font-bold text-white uppercase tracking-wider">
                        Linked Physical Issue Clustered
                      </span>
                    </div>
                    <span className="font-mono text-emerald-400 text-xs font-bold">
                      {record.associated_issue.issue_reference_id}
                    </span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                    <div className="bg-black/20 p-3 rounded-xl border border-white/5">
                      <span className="text-white/40 block text-[10px] uppercase">Cluster Status</span>
                      <span className="text-emerald-300 font-semibold">{record.associated_issue.current_status}</span>
                    </div>
                    <div className="bg-black/20 p-3 rounded-xl border border-white/5">
                      <span className="text-white/40 block text-[10px] uppercase">Reports in Cluster</span>
                      <span className="text-white font-bold">{record.associated_issue.complaint_count} citizen report(s)</span>
                    </div>
                    <div className="bg-black/20 p-3 rounded-xl border border-white/5">
                      <span className="text-white/40 block text-[10px] uppercase">Civic Category</span>
                      <span className="text-white font-semibold">{record.associated_issue.category}</span>
                    </div>
                  </div>

                  <p className="text-white/60 text-xs leading-relaxed">
                    Civic Impact: Your complaint is linked to a verified physical issue cluster. Multiple citizen reports reinforce prioritization without generating redundant repair tickets.
                  </p>
                </div>
              ) : record.duplicate_matches && record.duplicate_matches.length > 0 ? (
                <div className="border border-[#F36B21]/20 bg-[#F36B21]/[0.03] rounded-2xl p-5 space-y-3">
                  <div className="flex items-center gap-2 border-b border-[#F36B21]/10 pb-3">
                    <Layers size={16} className="text-[#F36B21]" />
                    <span className="text-xs font-bold text-white uppercase tracking-wider">
                      Potential Civic Issue Correlation Identified
                    </span>
                  </div>

                  {record.duplicate_matches.map((m) => (
                    <div key={m.id} className="bg-black/20 p-3.5 rounded-xl border border-white/5 space-y-2 text-xs">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="font-mono text-white/80 font-bold">
                          Candidate Issue: {m.candidate_physical_issue_id}
                        </span>
                        <div className="flex items-center gap-2">
                          <span className="bg-[#F36B21]/20 text-[#F36B21] px-2 py-0.5 rounded-full text-[10px] font-bold uppercase">
                            {Math.round(m.similarity_score * 100)}% Match ({m.confidence_level})
                          </span>
                          <span className="text-white/40 text-[10px] uppercase">
                            Status: {m.review_status}
                          </span>
                        </div>
                      </div>

                      <p className="text-white/60 text-[11px] leading-relaxed">
                        {m.matching_explanation}
                      </p>

                      <p className="text-white/40 text-[10px] pt-1">
                        Notice: Civic administrators are reviewing this correlation to coordinate joint physical resolution.
                      </p>
                    </div>
                  ))}
                </div>
              ) : null}
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      <Footer />
    </div>
  )
}

