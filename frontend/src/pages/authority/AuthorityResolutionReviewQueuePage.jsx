import React, { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  CheckSquare, Award, Clock, AlertTriangle, Filter,
  RefreshCw, ChevronRight, Eye, ShieldCheck, Building2,
  FileText, CheckCircle2, XCircle, RotateCcw, Sparkles
} from 'lucide-react'
import AuthorityLayout from '../../components/AuthorityLayout'
import { useAuth } from '../../context/AuthContext'
import { formatToIST } from '../../utils/dateTime'

export default function AuthorityResolutionReviewQueuePage() {
  const { authFetch, user } = useAuth()
  const navigate = useNavigate()
  const [submissions, setSubmissions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [statusFilter, setStatusFilter] = useState('submitted')
  const [deptFilter, setDeptFilter] = useState('')

  const fetchSubmissions = async () => {
    setLoading(true)
    setError(null)
    try {
      let url = '/api/authority/resolutions/queue?'
      const params = new URLSearchParams()
      if (statusFilter && statusFilter !== 'all') {
        params.append('status', statusFilter)
      }
      if (deptFilter) {
        params.append('department_id', deptFilter)
      }
      url += params.toString()

      const res = await authFetch(url)
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}))
        throw new Error(errJson.detail || 'Failed to load resolution submissions.')
      }
      const data = await res.json()
      setSubmissions(data.items || [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchSubmissions()
  }, [statusFilter, deptFilter])

  const pendingCount = submissions.filter(s => s.status === 'submitted').length

  return (
    <AuthorityLayout
      pageTitle="Resolution Verification Queue"
      breadcrumbs={['Authority', 'Resolution Review Queue']}
    >
      <div className="space-y-8 max-w-7xl mx-auto font-sans pb-12">
        {/* Top Header Card */}
        <div className="relative rounded-3xl bg-[#141722]/85 border border-white/[0.08] p-6 sm:p-8 backdrop-blur-xl overflow-hidden shadow-2xl">
          <div className="absolute top-0 right-1/4 w-96 h-96 bg-gradient-to-b from-[#138A4B]/15 via-[#102B4E]/20 to-transparent rounded-full blur-[110px] pointer-events-none" />

          <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
            <div>
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#10131C] border border-white/[0.08] text-[11px] font-semibold text-[#A1A1AA] mb-3 shadow-xs">
                <ShieldCheck className="w-3.5 h-3.5 text-[#138A4B]" />
                <span className="uppercase tracking-wider">Phase 8 • Evidence-Based Verification</span>
                <span>•</span>
                <span className="text-[#F36B21]">{pendingCount} Awaiting Review</span>
              </div>
              <h1 className="text-2xl sm:text-3xl font-extrabold text-[#F5F5F5] tracking-tight">
                Resolution Verification Queue
              </h1>
              <p className="text-xs sm:text-sm text-[#A1A1AA] mt-2 max-w-3xl leading-relaxed">
                Review completed municipal field repairs before official closure. Department officers submit evidence of completion; Authority Officers conduct independent evidence verification to ensure municipal accountability.
              </p>
            </div>

            {/* Filters */}
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex items-center gap-2 bg-[#10131C] border border-white/[0.08] rounded-xl px-3 py-2 text-xs">
                <CheckSquare className="w-3.5 h-3.5 text-[#A1A1AA]" />
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="bg-transparent text-[#F5F5F5] font-semibold focus:outline-hidden cursor-pointer"
                >
                  <option value="submitted" className="bg-[#10131C]">Pending Review</option>
                  <option value="approved" className="bg-[#10131C]">Approved & Closed</option>
                  <option value="needs_correction" className="bg-[#10131C]">Returned for Correction</option>
                  <option value="all" className="bg-[#10131C]">All Submissions</option>
                </select>
              </div>

              <div className="flex items-center gap-2 bg-[#10131C] border border-white/[0.08] rounded-xl px-3 py-2 text-xs">
                <Building2 className="w-3.5 h-3.5 text-[#A1A1AA]" />
                <select
                  value={deptFilter}
                  onChange={(e) => setDeptFilter(e.target.value)}
                  className="bg-transparent text-[#F5F5F5] font-semibold focus:outline-hidden cursor-pointer"
                >
                  <option value="" className="bg-[#10131C]">All Departments</option>
                  <option value="1" className="bg-[#10131C]">Roads & Public Works</option>
                  <option value="2" className="bg-[#10131C]">Sanitation & Waste</option>
                  <option value="3" className="bg-[#10131C]">Water Supply & Sewerage</option>
                  <option value="4" className="bg-[#10131C]">Storm Water Drainage</option>
                  <option value="5" className="bg-[#10131C]">Electrical & Street Lighting</option>
                  <option value="6" className="bg-[#10131C]">Parks & Infrastructure</option>
                </select>
              </div>

              <button
                onClick={fetchSubmissions}
                disabled={loading}
                className="px-4 py-2 rounded-xl bg-white/[0.06] hover:bg-white/[0.12] border border-white/[0.08] text-[#F5F5F5] text-xs font-semibold flex items-center gap-2 cursor-pointer transition-all"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-[#F36B21]' : 'text-[#A1A1AA]'}`} />
                <span>Sync</span>
              </button>
            </div>
          </div>
        </div>

        {error && (
          <div className="p-4 rounded-2xl bg-red-500/10 border border-red-500/30 text-red-400 text-xs flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
            <button onClick={fetchSubmissions} className="underline font-semibold cursor-pointer">
              Retry
            </button>
          </div>
        )}

        {/* Submissions List */}
        <div className="bg-[#141722]/85 rounded-3xl border border-white/[0.08] p-6 shadow-xl">
          <div className="flex items-center justify-between mb-5">
            <div>
              <h2 className="text-base font-bold text-[#F5F5F5]">Field Resolution Dossiers</h2>
              <p className="text-xs text-[#A1A1AA] mt-0.5">
                Work orders completed by department field teams awaiting Authority Officer inspection and closure.
              </p>
            </div>
            <div className="text-xs text-[#A1A1AA] font-mono">
              {submissions.length} Submissions Listed
            </div>
          </div>

          {loading ? (
            <div className="py-20 text-center">
              <RefreshCw className="w-7 h-7 text-[#F36B21] animate-spin mx-auto mb-2" />
              <p className="text-xs text-[#A1A1AA]">Loading resolution dossiers...</p>
            </div>
          ) : submissions.length === 0 ? (
            <div className="py-16 text-center text-xs text-[#A1A1AA]">
              No resolution dossiers match the selected filter criteria.
            </div>
          ) : (
            <div className="space-y-4">
              {submissions.map((sub) => {
                const isPending = sub.status === 'submitted'
                const isApproved = sub.status === 'approved'
                const isCorrection = sub.status === 'needs_correction'

                return (
                  <div
                    key={sub.id}
                    className="p-5 rounded-2xl bg-[#10131C] border border-white/[0.06] hover:border-white/[0.15] transition-all flex flex-col md:flex-row md:items-center justify-between gap-4"
                  >
                    <div className="space-y-2 flex-1 min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono font-bold text-xs text-[#F36B21]">
                          {sub.complaint?.complaint_id || `JS-${sub.complaint_id}`}
                        </span>
                        <span className="text-[10px] px-2 py-0.5 rounded-md bg-[#141722] text-[#A1A1AA] border border-white/[0.08] font-mono font-bold">
                          v{sub.version_number}
                        </span>
                        <span className="text-[10px] px-2 py-0.5 rounded-md bg-[#141722] text-zinc-300 border border-white/[0.08]">
                          {sub.complaint?.department_name || 'Municipal Works'}
                        </span>

                        {isPending && (
                          <span className="text-[10px] px-2.5 py-0.5 rounded-full bg-amber-500/15 text-amber-400 border border-amber-500/30 font-bold">
                            Pending Authority Review
                          </span>
                        )}
                        {isApproved && (
                          <span className="text-[10px] px-2.5 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 font-bold">
                            Verified & Closed
                          </span>
                        )}
                        {isCorrection && (
                          <span className="text-[10px] px-2.5 py-0.5 rounded-full bg-red-500/15 text-red-400 border border-red-500/30 font-bold">
                            Returned for Correction
                          </span>
                        )}
                      </div>

                      <div>
                        <div className="text-sm font-bold text-[#F5F5F5] truncate">
                          {sub.work_description || sub.repair_action_taken || 'Field Resolution Report'}
                        </div>
                        <p className="text-xs text-[#A1A1AA] line-clamp-1 mt-0.5">
                          {sub.repair_action_taken || sub.field_notes || 'No description provided.'}
                        </p>
                      </div>

                      <div className="flex flex-wrap items-center gap-4 text-[10px] text-[#A1A1AA] font-mono pt-1">
                        <span>Submitted: {formatToIST(sub.created_at)}</span>
                        <span>•</span>
                        <span>Officer: {sub.submitted_by_officer_name || 'Field Officer'}</span>
                        <span>•</span>
                        <span>Evidence: {sub.after_photo_urls?.length || 0} Photos Attached</span>
                        {sub.ai_analysis && (
                          <>
                            <span>•</span>
                            <span className="text-sky-400 flex items-center gap-1">
                              <Sparkles className="w-3 h-3" />
                              AI Verified: {sub.ai_analysis.work_completion_likelihood || 'Advisory'}
                            </span>
                          </>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-3 flex-shrink-0">
                      <Link
                        to={`/authority/resolution-review/${sub.id}`}
                        className="px-4 py-2 rounded-xl bg-[#F36B21] hover:bg-[#E05A10] text-white text-xs font-semibold flex items-center gap-1.5 shadow-md transition-all"
                      >
                        <Eye className="w-3.5 h-3.5" />
                        <span>Inspect Verification</span>
                        <ChevronRight className="w-3.5 h-3.5" />
                      </Link>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </AuthorityLayout>
  )
}
