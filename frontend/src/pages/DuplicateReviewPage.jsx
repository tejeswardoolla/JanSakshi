import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ArrowLeft,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Layers,
  MapPin,
  FileText,
  Clock,
  ShieldAlert,
  Search,
  Filter,
  RefreshCw,
  ExternalLink,
  ChevronRight,
  Info
} from 'lucide-react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import AuthorityLayout from '../components/AuthorityLayout'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import { formatToIST } from '../utils/dateTime'

export default function DuplicateReviewPage() {
  const { authFetch } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const isInternal = location.pathname.startsWith('/authority')

  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [statusFilter, setStatusFilter] = useState('pending')
  const [confidenceFilter, setConfidenceFilter] = useState('')
  const [actionLoading, setActionLoading] = useState(null)
  const [actionMessage, setActionMessage] = useState(null)
  const [reviewerName, setReviewerName] = useState('Municipal Officer')
  const [reviewNote, setReviewNote] = useState('')
  const [activeNoteModal, setActiveNoteModal] = useState(null)

  const fetchReviewQueue = async () => {
    setLoading(true)
    setError(null)
    try {
      let url = `/api/duplicates/review-queue?status=${statusFilter}`
      if (confidenceFilter) {
        url += `&confidence=${confidenceFilter}`
      }
      const res = await authFetch(url)
      const data = await res.json()
      if (res.ok) {
        setItems(data)
      } else {
        setError(data.detail || 'Failed to load review queue.')
      }
    } catch (err) {
      setError('Unable to reach server. Please ensure backend is operational.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchReviewQueue()
  }, [statusFilter, confidenceFilter])

  const handleAction = async (matchId, action, customReason = '') => {
    setActionLoading(matchId)
    setActionMessage(null)
    try {
      const endpoint = action === 'approve'
        ? `/api/duplicates/matches/${matchId}/approve`
        : `/api/duplicates/matches/${matchId}/reject`

      const payload = {
        reviewer_id: reviewerName || 'authority_officer',
        review_reason: customReason || (action === 'approve' ? 'Corroborated ground duplicate' : 'Distinct civic issue')
      }

      const res = await authFetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })

      const data = await res.json()

      if (res.ok) {
        setActionMessage({
          type: 'success',
          text: action === 'approve'
            ? `Successfully associated complaint with Physical Issue ${data.issue_reference_id}!`
            : 'Candidate rejected. Complaint preserved as independent civic record.'
        })
        fetchReviewQueue()
      } else {
        setActionMessage({ type: 'error', text: data.detail || 'Action failed.' })
      }
    } catch (err) {
      setActionMessage({ type: 'error', text: 'Network request failed.' })
    } finally {
      setActionLoading(null)
      setActiveNoteModal(null)
      setReviewNote('')
    }
  }

  const renderContent = () => (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 pb-6 border-b border-white/[0.08]">
        <div>
          <div className="inline-flex items-center gap-2 bg-[#F36B21]/15 border border-[#F36B21]/30 px-3 py-1 rounded-full mb-3">
            <Layers size={13} className="text-[#F36B21]" />
            <span className="text-[#F36B21] text-[11px] font-bold tracking-widest uppercase">
              Phase 5 Duplicate Detection & Physical Clustering
            </span>
          </div>
          <h1 className="text-3xl sm:text-4xl font-extrabold text-[#F5F5F5] tracking-tight">
            Civic Duplicate Review Queue
          </h1>
          <p className="text-[#A1A1AA] text-sm mt-2 max-w-2xl leading-relaxed">
            Verify AI-recommended physical issue correlations. JanSakshi multi-signal matching correlates independent citizen reports while strictly preserving original records, evidence, and coordinates.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchReviewQueue}
            disabled={loading}
            className="flex items-center gap-2 bg-[#141722]/85 hover:bg-[#191D2A] border border-white/[0.08] text-[#F5F5F5] px-4 py-2.5 rounded-xl text-xs font-semibold transition-all disabled:opacity-50 cursor-pointer shadow-sm"
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            <span>Refresh Queue</span>
          </button>
        </div>
      </div>

      {/* Global Toast / Notification */}
      <AnimatePresence>
        {actionMessage && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className={`p-4 rounded-2xl text-sm flex items-center justify-between border ${
              actionMessage.type === 'success'
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                : 'bg-rose-500/10 border-rose-500/30 text-rose-400'
            }`}
          >
            <div className="flex items-center gap-3">
              {actionMessage.type === 'success' ? (
                <CheckCircle2 size={18} className="text-emerald-400 shrink-0" />
              ) : (
                <AlertTriangle size={18} className="text-rose-400 shrink-0" />
              )}
              <span>{actionMessage.text}</span>
            </div>
            <button
              onClick={() => setActionMessage(null)}
              className="text-[#A1A1AA] hover:text-[#F5F5F5] text-xs ml-4 cursor-pointer"
            >
              Dismiss
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Filter and Control Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-2xl bg-[#141722]/85 backdrop-blur-xl border border-white/[0.08]">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-bold text-[#A1A1AA] uppercase tracking-wider mr-2 flex items-center gap-1.5">
            <Filter size={12} /> Status:
          </span>
          {['pending', 'approved', 'rejected'].map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`px-3 py-1.5 rounded-xl text-xs font-semibold capitalize transition-all cursor-pointer ${
                statusFilter === s
                  ? 'bg-[#F36B21] text-white shadow-md shadow-[#F36B21]/20'
                  : 'bg-[#10131C] hover:bg-white/[0.05] text-[#A1A1AA] hover:text-[#F5F5F5] border border-white/[0.08]'
              }`}
            >
              {s}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-3">
          <label className="text-xs font-semibold text-[#A1A1AA]">Confidence:</label>
          <select
            value={confidenceFilter}
            onChange={(e) => setConfidenceFilter(e.target.value)}
            className="bg-[#10131C] border border-white/[0.08] text-xs text-[#F5F5F5] px-3 py-1.5 rounded-xl focus:outline-none focus:border-[#F36B21]"
          >
            <option value="">All Levels</option>
            <option value="high">High (&gt;85%)</option>
            <option value="medium">Medium (70-85%)</option>
            <option value="low">Low (&lt;70%)</option>
          </select>
        </div>
      </div>

      {/* Review Queue Items */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-24 text-zinc-500">
          <RefreshCw size={28} className="animate-spin text-[#F36B21] mb-3" />
          <span className="text-sm font-medium">Scanning physical issues & duplicate candidates...</span>
        </div>
      ) : items.length === 0 ? (
        <div className="text-center py-20 px-6 rounded-3xl bg-[#141722]/85 border border-white/[0.08]">
          <Layers size={36} className="mx-auto text-zinc-600 mb-3" />
          <h3 className="text-lg font-bold text-[#F5F5F5] mb-1">Queue is Clear</h3>
          <p className="text-sm text-[#A1A1AA] max-w-md mx-auto">
            No duplicate candidates found matching the selected status '{statusFilter}'.
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {items.map((item) => {
            // Support both wrapped queue item { match, complaint_... } and direct match item
            const match = item.match || item
            const comp = {
              complaint_id: match.complaint_id,
              category: item.complaint_category || match.complaint?.category,
              description: item.complaint_description || match.complaint?.description,
              latitude: item.complaint_latitude ?? match.complaint?.latitude,
              longitude: item.complaint_longitude ?? match.complaint?.longitude,
              location_source: match.complaint?.location_source || 'gps'
            }
            const issue = match.candidate_issue || match.physical_issue || {}
            const isPending = match.review_status === 'pending'
            const isProcessing = actionLoading === match.id

            return (
              <div
                key={match.id}
                className="p-6 rounded-3xl bg-[#141722]/85 backdrop-blur-xl border border-white/[0.08] hover:border-white/[0.15] transition-all space-y-6 shadow-xl"
              >
                {/* Header */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-white/[0.06]">
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-sm font-bold text-[#F36B21]">
                      Match #{match.id}
                    </span>
                    <span className="text-xs px-2.5 py-0.5 rounded-full font-semibold bg-white/10 text-[#F5F5F5]">
                      Score: {(match.similarity_score * 100).toFixed(0)}% ({match.confidence_level})
                    </span>
                    <span
                      className={`text-xs px-2.5 py-0.5 rounded-full font-semibold uppercase ${
                        match.review_status === 'approved'
                          ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                          : match.review_status === 'rejected'
                          ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                          : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                      }`}
                    >
                      {match.review_status}
                    </span>
                  </div>

                  <span className="text-xs text-[#A1A1AA] font-mono">
                    Detected {formatToIST(match.created_at)}
                  </span>
                </div>

                {/* Comparison Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Incoming Complaint */}
                  <div className="p-4 rounded-2xl bg-[#10131C] border border-white/[0.06] space-y-3">
                    <div className="flex items-center justify-between text-xs font-semibold text-[#A1A1AA]">
                      <span className="flex items-center gap-1.5 text-[#F5F5F5]">
                        <FileText size={13} className="text-[#F36B21]" /> Incoming Complaint
                      </span>
                      <span className="font-mono text-[#F36B21]">{comp.complaint_id}</span>
                    </div>

                    <div className="text-sm font-bold text-[#F5F5F5]">{comp.category}</div>
                    <p className="text-xs text-[#A1A1AA] line-clamp-3 leading-relaxed">
                      {comp.description}
                    </p>

                    <div className="pt-2 border-t border-white/5 flex items-center gap-1.5 text-xs text-[#A1A1AA]">
                      <MapPin size={12} className="text-zinc-500" />
                      <span>{comp.latitude ? `${comp.latitude.toFixed(4)}, ${comp.longitude.toFixed(4)}` : 'No GPS'}</span>
                      <span className="text-[10px] text-zinc-500 ml-auto capitalize">{comp.location_source}</span>
                    </div>
                  </div>

                  {/* Candidate Physical Issue */}
                  <div className="p-4 rounded-2xl bg-[#10131C] border border-white/[0.06] space-y-3">
                    <div className="flex items-center justify-between text-xs font-semibold text-[#A1A1AA]">
                      <span className="flex items-center gap-1.5 text-[#F5F5F5]">
                        <Layers size={13} className="text-sky-400" /> Correlated Physical Issue
                      </span>
                      <span className="font-mono text-sky-400">{issue.issue_reference_id}</span>
                    </div>

                    <div className="text-sm font-bold text-[#F5F5F5]">{issue.category}</div>
                    <div className="text-xs text-[#A1A1AA] leading-relaxed">
                      Status: <strong className="text-[#F5F5F5]">{issue.current_status}</strong> • Linked Complaints: <strong className="text-[#F5F5F5]">{issue.complaint_count || issue.complaints?.length || 1}</strong>
                    </div>

                    <div className="pt-2 border-t border-white/5 flex items-center gap-1.5 text-xs text-[#A1A1AA]">
                      <MapPin size={12} className="text-zinc-500" />
                      <span>{issue.representative_location || 'Municipal Geocoded Marker'}</span>
                    </div>
                  </div>
                </div>

                {/* AI Recommendation Reason */}
                <div className="p-3.5 rounded-xl bg-[#F36B21]/10 border border-[#F36B21]/20 text-xs text-[#F5F5F5] space-y-1">
                  <div className="font-bold text-[#F36B21] flex items-center gap-1.5">
                    <Info size={13} /> Matching Analysis
                  </div>
                  <p className="text-[#A1A1AA] leading-relaxed">{match.matching_explanation}</p>
                </div>

                {/* Actions (for Pending matches) */}
                {isPending && (
                  <div className="pt-2 flex items-center justify-end gap-3">
                    <button
                      onClick={() => handleAction(match.id, 'reject', 'Admin rejected correlation')}
                      disabled={isProcessing}
                      className="px-4 py-2 rounded-xl bg-white/5 hover:bg-rose-500/20 text-rose-300 border border-white/10 hover:border-rose-500/40 text-xs font-semibold flex items-center gap-1.5 transition-all cursor-pointer disabled:opacity-50"
                    >
                      <XCircle size={14} />
                      <span>Reject Candidate</span>
                    </button>
                    <button
                      onClick={() => handleAction(match.id, 'approve', 'Admin approved physical clustering')}
                      disabled={isProcessing}
                      className="px-5 py-2 rounded-xl bg-[#138A4B] hover:bg-[#10703D] text-white text-xs font-semibold flex items-center gap-1.5 shadow-sm transition-all cursor-pointer disabled:opacity-50"
                    >
                      <CheckCircle2 size={14} />
                      <span>Confirm & Associate</span>
                    </button>
                  </div>
                )}

                {!isPending && (
                  <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 pt-4 border-t border-white/5 text-[11px] text-[#A1A1AA]">
                    <div>
                      <span>Reviewed by: </span>
                      <strong className="text-[#F5F5F5]">{match.reviewer_id || 'authority_reviewer'}</strong>
                      {match.reviewed_at && (
                        <span> on {formatToIST(match.reviewed_at)}</span>
                      )}
                    </div>
                    {match.review_reason && (
                      <p className="italic text-[#A1A1AA]">"{match.review_reason}"</p>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )

  if (isInternal) {
    return (
      <AuthorityLayout pageTitle="Duplicate Review Desk" breadcrumbs={['Admin', 'Duplicate Review']}>
        {renderContent()}
      </AuthorityLayout>
    )
  }

  return (
    <div className="min-h-screen bg-[#08090B] flex flex-col selection:bg-[#F36B21] selection:text-white">
      <Navbar />
      <main className="flex-1 max-w-7xl mx-auto w-full px-6 pt-32 pb-24">
        {renderContent()}
      </main>
      <Footer />
    </div>
  )
}
