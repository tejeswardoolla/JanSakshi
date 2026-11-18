import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  History, Search, Filter, RefreshCw, ChevronLeft, ChevronRight,
  Shield, ExternalLink, ArrowRight
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { getApiUrl } from '../config/api'
import AuthorityLayout from '../components/AuthorityLayout'
import { formatToIST, formatISTDateOnly } from '../utils/dateTime'

export default function AuthorityAuditPage() {
  const { authFetch, user } = useAuth()
  const [events, setEvents] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [limit] = useState(20)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [searchId, setSearchId] = useState('')
  const [eventType, setEventType] = useState('')

  const isDeptOfficer = user?.role === 'department_officer'
  const activeDeptId = localStorage.getItem('jansakshi_active_dept_id') || (user?.department_id || 1).toString()
  const activeDeptCode = localStorage.getItem('jansakshi_active_dept_code') || user?.department_code || 'RPW'
  const activeDeptName = localStorage.getItem('jansakshi_active_dept_name') || 'Roads & Public Works'

  useEffect(() => {
    fetchAuditEvents()
  }, [page, eventType])

  const fetchAuditEvents = async () => {
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams({
        page: page.toString(),
        limit: limit.toString()
      })
      if (searchId.trim()) params.append('complaint_id', searchId.trim())
      if (eventType) params.append('event_type', eventType)
      if (isDeptOfficer) params.append('department_id', activeDeptId.toString())

      const res = await authFetch(getApiUrl(`/api/authority/audit?${params.toString()}`))
      if (!res.ok) throw new Error('Failed to load audit history.')
      const data = await res.json()
      setEvents(data.items || [])
      setTotal(data.total || 0)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleSearchSubmit = (e) => {
    e.preventDefault()
    setPage(1)
    fetchAuditEvents()
  }

  const totalPages = Math.ceil(total / limit) || 1

  return (
    <AuthorityLayout
      pageTitle={isDeptOfficer ? (activeDeptCode === 'RPW' ? "Roads Division Activity & Work Order Log" : `${activeDeptName} (${activeDeptCode}) Activity Log`) : "System Audit & Event Trail"}
      breadcrumbs={isDeptOfficer ? [activeDeptName, 'Division Activity'] : ['Administration', 'Audit History']}
    >
      <div className="space-y-6 max-w-7xl">
        {/* Search & Filter Header */}
        <div className="bg-[#141722]/85 backdrop-blur-xl border border-white/[0.08] rounded-3xl p-6 shadow-xl space-y-4">
          <form onSubmit={handleSearchSubmit} className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <Search className="w-4 h-4 text-[#A1A1AA] absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={searchId}
                onChange={(e) => setSearchId(e.target.value)}
                placeholder={isDeptOfficer ? "Filter by assigned Road Complaint ID (e.g. JS-2026-00019)..." : "Filter by Complaint ID (e.g. JS-2026-00019)..."}
                className="w-full pl-10 pr-4 py-2.5 bg-[#10131C] border border-white/[0.08] rounded-xl text-xs text-[#F5F5F5] placeholder-[#A1A1AA]/50 focus:outline-none focus:border-[#F36B21]"
              />
            </div>

            <div className="w-full sm:w-64">
              <select
                value={eventType}
                onChange={(e) => { setEventType(e.target.value); setPage(1) }}
                className="w-full py-2.5 px-3 bg-[#10131C] border border-white/[0.08] rounded-xl text-xs text-[#F5F5F5] focus:outline-none focus:border-[#F36B21]"
              >
                <option value="">All Event Types</option>
                <option value="verification">Verification Actions</option>
                <option value="department">Department Assignments</option>
                <option value="escalat">Escalations</option>
                <option value="status">Status Changes</option>
                <option value="note">Internal Notes</option>
                <option value="email">Email Ingestion</option>
              </select>
            </div>

            <button
              type="submit"
              className="px-5 py-2.5 bg-[#F36B21] hover:bg-[#E05A10] text-white rounded-xl text-xs font-semibold flex items-center justify-center gap-2 cursor-pointer shadow-md shadow-[#F36B21]/20 transition-all"
            >
              <Search className="w-3.5 h-3.5" />
              <span>Search</span>
            </button>

            {(searchId || eventType) && (
              <button
                type="button"
                onClick={() => { setSearchId(''); setEventType(''); setPage(1) }}
                className="px-4 py-2.5 bg-white/5 hover:bg-white/10 border border-white/10 text-white/70 rounded-xl text-xs cursor-pointer"
              >
                Reset
              </button>
            )}
          </form>
        </div>

        {/* Audit Events Timeline / Table */}
        <div className="bg-[#141722]/85 backdrop-blur-xl border border-white/[0.08] rounded-3xl overflow-hidden shadow-2xl">
          {loading ? (
            <div className="py-20 text-center">
              <RefreshCw className="w-8 h-8 text-[#F36B21] animate-spin mx-auto mb-3" />
              <p className="text-xs text-[#A1A1AA] font-mono">Loading chronological audit records...</p>
            </div>
          ) : events.length === 0 ? (
            <div className="py-20 text-center">
              <History className="w-10 h-10 text-zinc-600 mx-auto mb-3" />
              <h3 className="text-sm font-semibold text-[#F5F5F5]">No Audit Events Found</h3>
              <p className="text-xs text-[#A1A1AA] mt-1 font-mono">No actions match your filter criteria.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="bg-[#10131C] border-b border-white/[0.08] text-[#A1A1AA] font-mono uppercase text-[11px]">
                    <th className="py-3.5 px-4">Timestamp</th>
                    <th className="py-3.5 px-4">Complaint ID</th>
                    <th className="py-3.5 px-4">Action Type</th>
                    <th className="py-3.5 px-4">Event Description</th>
                    <th className="py-3.5 px-4">Source</th>
                    <th className="py-3.5 px-4 text-center">Inspect</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/[0.06]">
                  {events.map((ev) => (
                    <tr key={ev.id} className="hover:bg-white/[0.02] transition-colors">
                      <td className="py-3.5 px-4 whitespace-nowrap font-mono text-[#A1A1AA] text-[11px]">
                        {formatToIST(ev.created_at)}
                      </td>

                      <td className="py-3.5 px-4 whitespace-nowrap">
                        <Link
                          to={`/authority/complaints/${ev.complaint_id}`}
                          className="font-mono font-bold text-[#F36B21] hover:underline"
                        >
                          {ev.complaint_id}
                        </Link>
                      </td>

                      <td className="py-3.5 px-4 whitespace-nowrap">
                        <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-white/10 text-[#F5F5F5]">
                          {ev.event_type}
                        </span>
                      </td>

                      <td className="py-3.5 px-4 max-w-md">
                        <p className="text-[#F5F5F5] leading-relaxed">{ev.description}</p>
                        {(ev.previous_value || ev.new_value) && (
                          <div className="flex items-center gap-2 mt-1 text-[10px] text-[#A1A1AA] font-mono">
                            {ev.previous_value && <span>From: {ev.previous_value}</span>}
                            {ev.previous_value && ev.new_value && <span>→</span>}
                            {ev.new_value && <span className="text-[#F5F5F5] font-semibold">To: {ev.new_value}</span>}
                          </div>
                        )}
                      </td>

                      <td className="py-3.5 px-4 whitespace-nowrap font-mono text-[11px] text-[#A1A1AA] uppercase">
                        {ev.source}
                      </td>

                      <td className="py-3.5 px-4 text-center whitespace-nowrap">
                        <Link
                          to={`/authority/complaints/${ev.complaint_id}`}
                          className="p-1.5 rounded-lg bg-[#10131C] hover:bg-white/10 border border-white/[0.08] text-[#F5F5F5] inline-flex items-center gap-1 transition-all"
                        >
                          <ExternalLink className="w-3.5 h-3.5" />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination */}
          <div className="p-4 border-t border-white/[0.08] flex items-center justify-between text-xs text-[#A1A1AA]">
            <span>
              Showing {events.length} of {total} audit records (Page <strong className="text-[#F5F5F5] font-mono">{page}</strong> of <strong className="text-[#F5F5F5] font-mono">{totalPages}</strong>)
            </span>

            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="p-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 disabled:opacity-30 disabled:cursor-not-allowed text-[#F5F5F5]"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="p-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 disabled:opacity-30 disabled:cursor-not-allowed text-[#F5F5F5]"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </AuthorityLayout>
  )
}

