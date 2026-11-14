import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  CheckCircle, XCircle, HelpCircle, Eye, Clock, RefreshCw,
  AlertCircle, MapPin, Mail, Globe, ArrowRight, CheckCircle2,
  Shield, Check
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import AuthorityLayout from '../components/AuthorityLayout'
import RoadInspectionQueuePage from './RoadInspectionQueuePage'
import { formatISTDateOnly } from '../utils/dateTime'

export default function AuthorityVerificationQueuePage() {
  const { authFetch, user } = useAuth()

  // Department officer must not see citizen verification queue
  if (user?.role === 'department_officer') {
    return <RoadInspectionQueuePage />
  }

  const [complaints, setComplaints] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [actionSuccess, setActionSuccess] = useState(null)

  // Action modal states
  const [activeModal, setActiveModal] = useState(null) // 'verify', 'reject', 'request_info'
  const [targetId, setTargetId] = useState(null)
  const [verifyNotes, setVerifyNotes] = useState('')
  const [rejectReason, setRejectReason] = useState('')
  const [infoNotes, setInfoNotes] = useState('')
  const [actionLoading, setActionLoading] = useState(false)

  useEffect(() => {
    fetchPendingComplaints()
  }, [])

  const fetchPendingComplaints = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await authFetch('http://127.0.0.1:8000/api/authority/complaints?verification_status=pending&limit=50')
      if (!res.ok) throw new Error('Failed to load verification queue.')
      const data = await res.json()
      setComplaints(data.items || [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleVerify = async () => {
    setActionLoading(true)
    try {
      const res = await authFetch(`http://127.0.0.1:8000/api/authority/complaints/${targetId}/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ notes: verifyNotes })
      })
      if (!res.ok) throw new Error('Failed to verify complaint.')
      setActionSuccess(`Complaint ${targetId} verified successfully!`)
      setActiveModal(null)
      fetchPendingComplaints()
    } catch (err) {
      alert(err.message)
    } finally {
      setActionLoading(false)
    }
  }

  const handleReject = async () => {
    if (!rejectReason.trim()) {
      alert('Please provide a mandatory justification.')
      return
    }
    setActionLoading(true)
    try {
      const res = await authFetch(`http://127.0.0.1:8000/api/authority/complaints/${targetId}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: rejectReason })
      })
      if (!res.ok) throw new Error('Failed to reject complaint.')
      setActionSuccess(`Complaint ${targetId} rejected.`)
      setActiveModal(null)
      fetchPendingComplaints()
    } catch (err) {
      alert(err.message)
    } finally {
      setActionLoading(false)
    }
  }

  const handleRequestInfo = async () => {
    if (!infoNotes.trim()) {
      alert('Please specify the required details.')
      return
    }
    setActionLoading(true)
    try {
      const res = await authFetch(`http://127.0.0.1:8000/api/authority/complaints/${targetId}/request-info`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ notes: infoNotes })
      })
      if (!res.ok) throw new Error('Failed to request additional info.')
      setActionSuccess(`Information request dispatched for ${targetId}.`)
      setActiveModal(null)
      fetchPendingComplaints()
    } catch (err) {
      alert(err.message)
    } finally {
      setActionLoading(false)
    }
  }

  return (
    <AuthorityLayout
      pageTitle="Civic Decision Queue"
      breadcrumbs={['Operations Desk', 'Assignment Queue']}
    >
      <div className="space-y-6 max-w-7xl mx-auto font-sans">
        {/* Banner */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-6 rounded-3xl bg-amber-500/10/80 border border-amber-500/30 text-xs">
          <div className="flex items-center gap-3">
            <Clock className="w-5 h-5 text-amber-600 flex-shrink-0" />
            <div>
              <p className="font-bold text-amber-900 text-sm">Human Civic Decision Required</p>
              <p className="text-amber-800/80 mt-0.5">
                Review citizen complaints prepared by Admin before dispatching to municipal engineering divisions.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className="font-bold text-xs text-amber-900 bg-amber-100 px-3.5 py-1 rounded-full border border-amber-500/30">
              {complaints.length} Pending Decision
            </span>
            <button
              onClick={fetchPendingComplaints}
              className="p-2 rounded-xl bg-[#141722]/85 hover:bg-white/[0.03] border border-amber-500/30 text-amber-900 cursor-pointer shadow-xs transition-colors"
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

        {/* Complaints Table */}
        <div className="bg-[#141722]/85 rounded-3xl border border-white/[0.08] overflow-hidden shadow-xs">
          {loading ? (
            <div className="py-20 text-center">
              <RefreshCw className="w-8 h-8 text-[#F36B21] animate-spin mx-auto mb-3" />
              <p className="text-xs text-[#A1A1AA] font-medium">Loading pending decision items...</p>
            </div>
          ) : complaints.length === 0 ? (
            <div className="py-20 text-center">
              <CheckCircle className="w-10 h-10 text-emerald-500 mx-auto mb-3" />
              <h3 className="text-sm font-bold text-[#F5F5F5]">Decision Queue Cleared</h3>
              <p className="text-xs text-[#A1A1AA] mt-1">
                All submitted complaints have been reviewed and verified.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="bg-[#10131C] border-b border-white/[0.08] text-[#A1A1AA] font-bold uppercase text-[10px] tracking-wider">
                    <th className="py-3.5 px-4">Complaint ID</th>
                    <th className="py-3.5 px-4">Category</th>
                    <th className="py-3.5 px-4">Citizen Description</th>
                    <th className="py-3.5 px-4">Intake Readiness</th>
                    <th className="py-3.5 px-4">Evidence</th>
                    <th className="py-3.5 px-4 text-center">Civic Decision</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/[0.08]">
                  {complaints.map((c) => (
                    <tr key={c.complaint_id} className="hover:bg-[#10131C]/60 transition-colors group">
                      <td className="py-3.5 px-4 whitespace-nowrap">
                        <Link
                          to={`/authority/complaints/${c.complaint_id}`}
                          className="font-bold text-[#F5F5F5] group-hover:text-[#F36B21] transition-colors"
                        >
                          {c.complaint_id}
                        </Link>
                        <div className="text-[10px] text-zinc-500 mt-0.5">
                          {c.created_at ? formatISTDateOnly(c.created_at) : ''}
                        </div>
                      </td>

                      <td className="py-3.5 px-4 whitespace-nowrap">
                        <span className="font-semibold text-[#F5F5F5]">{c.category}</span>
                        {c.google_maps_url ? (
                          <div className="flex items-center gap-1 text-[10px] text-emerald-400 font-medium mt-0.5">
                            <MapPin className="w-3 h-3" />
                            <span>GPS Mapped</span>
                          </div>
                        ) : (
                          <div className="text-[10px] text-zinc-500 mt-0.5">Approximate</div>
                        )}
                      </td>

                      <td className="py-3.5 px-4 max-w-sm">
                        <p className="text-[#A1A1AA] line-clamp-2 leading-relaxed">{c.description}</p>
                      </td>

                      <td className="py-3.5 px-4 whitespace-nowrap">
                        {c.admin_status === 'Ready for Authority Officer' ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                            <Check className="w-3 h-3" />
                            <span>Ready for Decision</span>
                          </span>
                        ) : c.latitude && c.longitude ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-sky-500/10 text-sky-400 border border-sky-500/30">
                            <MapPin className="w-3 h-3" />
                            <span>Location Verified</span>
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-zinc-500/10 text-zinc-400 border border-zinc-500/30">
                            <span>{c.admin_status || 'Pending Intake'}</span>
                          </span>
                        )}
                      </td>

                      <td className="py-3.5 px-4 whitespace-nowrap text-[#A1A1AA] font-medium">
                        {c.evidence_count} file(s)
                      </td>

                      <td className="py-3.5 px-4 text-center whitespace-nowrap">
                        <div className="flex items-center justify-center gap-1.5">
                          <button
                            onClick={() => {
                              setTargetId(c.complaint_id)
                              setVerifyNotes('')
                              setActiveModal('verify')
                            }}
                            className="px-2.5 py-1 rounded-lg bg-[#138A4B] hover:bg-[#16A34A] text-white text-[11px] font-semibold flex items-center gap-1 shadow-xs cursor-pointer"
                          >
                            <Check className="w-3 h-3" />
                            <span>Accept</span>
                          </button>
                          <button
                            onClick={() => {
                              setTargetId(c.complaint_id)
                              setRejectReason('')
                              setActiveModal('reject')
                            }}
                            className="px-2 py-1 rounded-lg bg-red-500/10 hover:bg-red-100 text-red-400 border border-red-500/30 text-[11px] font-semibold cursor-pointer"
                          >
                            Reject
                          </button>
                          <Link
                            to={`/authority/complaints/${c.complaint_id}`}
                            className="px-2 py-1 rounded-lg bg-white/[0.05] hover:bg-white/[0.1] text-zinc-300 text-[11px] font-semibold"
                          >
                            Inspect
                          </Link>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Modal: Verify */}
        {activeModal === 'verify' && (
          <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div className="bg-[#141722]/85 rounded-3xl p-6 max-w-md w-full border border-white/[0.08] shadow-2xl space-y-4">
              <h3 className="text-base font-bold text-[#F5F5F5]">Approve Civic Verification</h3>
              <p className="text-xs text-[#A1A1AA]">
                Confirm acceptance of complaint {targetId} for municipal departmental action.
              </p>
              <textarea
                rows={3}
                value={verifyNotes}
                onChange={(e) => setVerifyNotes(e.target.value)}
                placeholder="Optional verification notes (e.g. Confirmed genuine pothole risk)..."
                className="w-full p-3 rounded-xl bg-[#10131C] border border-white/[0.08] text-xs text-[#F5F5F5]"
              />
              <div className="flex justify-end gap-2 pt-2">
                <button onClick={() => setActiveModal(null)} className="px-4 py-2 text-xs font-semibold text-[#A1A1AA]">Cancel</button>
                <button
                  onClick={handleVerify}
                  disabled={actionLoading}
                  className="px-4 py-2 rounded-xl bg-[#138A4B] text-white text-xs font-semibold"
                >
                  Confirm Acceptance
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Modal: Reject */}
        {activeModal === 'reject' && (
          <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div className="bg-[#141722]/85 rounded-3xl p-6 max-w-md w-full border border-white/[0.08] shadow-2xl space-y-4">
              <h3 className="text-base font-bold text-[#F5F5F5]">Reject Complaint</h3>
              <p className="text-xs text-[#A1A1AA]">
                Mandatory justification for rejecting complaint {targetId}.
              </p>
              <textarea
                required
                rows={3}
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="Reason for rejection (e.g. Outside municipal jurisdiction)..."
                className="w-full p-3 rounded-xl bg-[#10131C] border border-white/[0.08] text-xs text-[#F5F5F5]"
              />
              <div className="flex justify-end gap-2 pt-2">
                <button onClick={() => setActiveModal(null)} className="px-4 py-2 text-xs font-semibold text-[#A1A1AA]">Cancel</button>
                <button
                  onClick={handleReject}
                  disabled={actionLoading}
                  className="px-4 py-2 rounded-xl bg-[#DC2626] text-white text-xs font-semibold"
                >
                  Confirm Rejection
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </AuthorityLayout>
  )
}
