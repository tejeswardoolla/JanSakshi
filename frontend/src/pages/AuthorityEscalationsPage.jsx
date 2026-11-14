import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  Flame, AlertTriangle, Eye, Clock, Shield, RefreshCw,
  Building2, ArrowRight, CheckCircle2
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import AuthorityLayout from '../components/AuthorityLayout'
import { formatToIST } from '../utils/dateTime'

export default function AuthorityEscalationsPage() {
  const { authFetch } = useAuth()
  const [complaints, setComplaints] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchEscalated()
  }, [])

  const fetchEscalated = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await authFetch('http://127.0.0.1:8000/api/authority/complaints?escalation_level=1&limit=50')
      if (!res.ok) throw new Error('Failed to load escalations.')
      const data = await res.json()
      setComplaints(data.items || [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthorityLayout
      pageTitle="Escalation Management"
      breadcrumbs={['Operations', 'Escalations']}
    >
      <div className="space-y-6 max-w-7xl">
        {/* Banner */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-6 rounded-3xl bg-red-500/10 border border-red-500/30 shadow-xl text-xs">
          <div className="flex items-center gap-3">
            <Flame className="w-5 h-5 text-red-400 animate-pulse flex-shrink-0" />
            <div>
              <p className="font-bold text-red-400 text-sm">High-Priority Escalation Monitoring</p>
              <p className="text-[#A1A1AA] mt-0.5">
                Tickets escalated to Tier 1 (Division Head / EE) or Tier 2 (Municipal Commissioner) requiring immediate administrative intervention.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className="font-mono text-xs font-bold text-red-400 bg-red-500/20 px-3.5 py-1.5 rounded-full border border-red-500/30">
              {complaints.length} Escalated
            </span>
            <button
              onClick={fetchEscalated}
              className="p-2 rounded-xl bg-[#141722]/85 hover:bg-[#191D2A] border border-white/[0.08] text-[#F5F5F5] cursor-pointer transition-colors shadow-sm"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {/* Complaints Grid */}
        <div className="space-y-4">
          {loading ? (
            <div className="py-20 text-center">
              <RefreshCw className="w-8 h-8 text-[#F36B21] animate-spin mx-auto mb-3" />
              <p className="text-xs text-[#A1A1AA] font-mono">Loading escalated complaint tickets...</p>
            </div>
          ) : complaints.length === 0 ? (
            <div className="py-20 text-center bg-[#141722]/85 backdrop-blur-xl border border-white/[0.08] rounded-3xl shadow-xl">
              <CheckCircle2 className="w-10 h-10 text-[#138A4B] mx-auto mb-3" />
              <h3 className="text-sm font-semibold text-[#F5F5F5]">No Escalated Complaints Active</h3>
              <p className="text-xs text-[#A1A1AA] mt-1 font-mono">
                All high-priority grievances are proceeding within standard municipal SLA limits.
              </p>
            </div>
          ) : (
            complaints.map((c) => (
              <div
                key={c.complaint_id}
                className="p-6 rounded-3xl bg-[#141722]/85 backdrop-blur-xl border border-white/[0.08] hover:border-red-500/40 shadow-xl transition-all text-xs space-y-4"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-white/[0.06] pb-3">
                  <div className="flex items-center gap-2.5 flex-wrap">
                    <Link
                      to={`/authority/complaints/${c.complaint_id}`}
                      className="font-mono font-bold text-sm text-[#F5F5F5] hover:text-[#F36B21] transition-colors"
                    >
                      {c.complaint_id}
                    </Link>
                    <span className="flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-red-600 text-white font-mono">
                      <Flame className="w-3 h-3" />
                      <span>Tier {c.escalation_level} Escalated</span>
                    </span>
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-white/10 text-[#F5F5F5]">
                      {c.category}
                    </span>
                  </div>

                  <span className="text-[10px] text-[#A1A1AA] font-mono">
                    Escalated on: {c.escalated_at ? formatToIST(c.escalated_at) : 'N/A'}
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="md:col-span-2 space-y-2">
                    <span className="text-[10px] text-[#A1A1AA] uppercase font-mono block">Citizen Grievance</span>
                    <p className="text-[#F5F5F5] leading-relaxed bg-[#10131C] p-3 rounded-xl border border-white/[0.06]">
                      {c.description}
                    </p>

                    <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300">
                      <span className="text-[10px] uppercase font-mono font-bold text-red-400 block mb-0.5">
                        Escalation Justification
                      </span>
                      <p>{c.escalation_reason || 'Urgent intervention requested by civic authority.'}</p>
                    </div>
                  </div>

                  <div className="space-y-3 bg-[#10131C] p-4 rounded-xl border border-white/[0.06] flex flex-col justify-between">
                    <div className="space-y-2">
                      <div>
                        <span className="text-[10px] text-[#A1A1AA] uppercase font-mono block">Higher Authority</span>
                        <p className="font-bold text-[#F5F5F5] mt-0.5">{c.escalated_to || 'Municipal Commissioner'}</p>
                      </div>

                      <div>
                        <span className="text-[10px] text-[#A1A1AA] uppercase font-mono block">Assigned Division</span>
                        <p className="font-mono text-[#F36B21] font-bold">
                          {c.department ? `${c.department.code} - ${c.department.name}` : 'Unassigned'}
                        </p>
                      </div>

                      <div>
                        <span className="text-[10px] text-[#A1A1AA] uppercase font-mono block">Lifecycle Status</span>
                        <span className="inline-block mt-0.5 px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-red-500/20 text-red-400 border border-red-500/30">
                          {c.admin_status || c.status}
                        </span>
                      </div>
                    </div>

                    <Link
                      to={`/authority/complaints/${c.complaint_id}`}
                      className="w-full flex items-center justify-center gap-1.5 py-2 rounded-xl bg-[#F36B21] hover:bg-[#E05A10] text-xs font-semibold text-white shadow-md shadow-[#F36B21]/20 transition-all"
                    >
                      <span>Review & Intervene</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </Link>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </AuthorityLayout>
  )
}

