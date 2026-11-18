import React, { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Search, Filter, ChevronLeft, ChevronRight, Eye, Shield,
  ArrowUpDown, CheckCircle, Clock, AlertTriangle, Flame,
  Building2, XCircle, RefreshCw, Mail, Globe, MapPin, CheckCircle2
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import AuthorityLayout from '../components/AuthorityLayout'
import { formatToIST, formatISTDateOnly } from '../utils/dateTime'

export default function AuthorityComplaintsPage() {
  const { isAuthenticated, authFetch, user } = useAuth()
  const navigate = useNavigate()

  const isDeptOfficer = user?.role === 'department_officer'
  const activeDeptId = localStorage.getItem('jansakshi_active_dept_id') || (user?.department_id || 1).toString()
  const activeDeptCode = localStorage.getItem('jansakshi_active_dept_code') || user?.department_code || 'RPW'
  const activeDeptName = localStorage.getItem('jansakshi_active_dept_name') || 'Roads & Public Works'

  const [complaints, setComplaints] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [limit] = useState(15)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Filters state
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('')
  const [status, setStatus] = useState('')
  const [verificationStatus, setVerificationStatus] = useState('')
  const [departmentId, setDepartmentId] = useState('')
  const [departments, setDepartments] = useState([])
  const [sortBy, setSortBy] = useState('created_at')
  const [sortDir, setSortDir] = useState('desc')

  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/authority/login')
      return
    }
    fetchDepartments()
  }, [isAuthenticated, navigate])

  useEffect(() => {
    if (isAuthenticated) {
      fetchComplaints()
    }
  }, [page, category, status, verificationStatus, departmentId, sortBy, sortDir, isAuthenticated])

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

  const fetchComplaints = async () => {
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams({
        page: page.toString(),
        limit: limit.toString(),
        sort_by: sortBy,
        sort_dir: sortDir
      })

      if (search.trim()) params.append('search', search.trim())
      if (category) params.append('category', category)
      if (status) params.append('status', status)
      if (verificationStatus) params.append('verification_status', verificationStatus)

      if (isDeptOfficer) {
        params.append('department_id', activeDeptId)
      } else if (departmentId) {
        params.append('department_id', departmentId)
      }

      const res = await authFetch(`/api/authority/complaints?${params.toString()}`)
      if (!res.ok) {
        throw new Error('Failed to load complaint records.')
      }
      const data = await res.json()
      setComplaints(data.items || [])
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
    fetchComplaints()
  }

  const totalPages = Math.ceil(total / limit) || 1

  const getVerificationBadge = (vStatus) => {
    switch (vStatus) {
      case 'verified':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
            <span>Verified</span>
          </span>
        )
      case 'rejected':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-red-500/10 text-red-400 border border-red-500/30">
            <XCircle className="w-3 h-3 text-red-600" />
            <span>Rejected</span>
          </span>
        )
      case 'info_requested':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-sky-500/10 text-sky-800 border border-sky-500/30">
            <AlertTriangle className="w-3 h-3 text-sky-600" />
            <span>Info Needed</span>
          </span>
        )
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/10 text-amber-800 border border-amber-500/30">
            <Clock className="w-3 h-3 text-amber-600" />
            <span>Pending Review</span>
          </span>
        )
    }
  }

  const getAdminStatusBadge = (adStatus) => {
    const s = adStatus || 'Received'
    let color = 'bg-white/[0.05] text-zinc-300 border-stone-200'
    if (s === 'Resolved') color = 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
    else if (s === 'In Progress') color = 'bg-sky-500/10 text-sky-800 border-sky-500/30'
    else if (s === 'Assigned') color = 'bg-indigo-50 text-indigo-800 border-indigo-200'
    else if (s === 'Ready for Authority Officer') color = 'bg-emerald-100 text-emerald-900 border-emerald-300 font-bold'
    else if (s === 'Escalated') color = 'bg-red-500/10 text-red-400 border-red-500/30 animate-pulse'
    else if (s === 'Awaiting Department Assignment') color = 'bg-purple-500/10 text-purple-800 border-purple-500/30'

    return (
      <span className={`px-2 py-0.5 rounded-md text-[10px] font-semibold border ${color}`}>
        {s}
      </span>
    )
  }

  return (
    <AuthorityLayout
      pageTitle={isDeptOfficer ? (activeDeptCode === 'RPW' ? "My Assigned Road Complaints" : `My Assigned ${activeDeptCode} Complaints`) : "Complaint Registry"}
      breadcrumbs={isDeptOfficer ? [activeDeptName, 'Assigned Work'] : ['Operations Desk', 'Complaints']}
    >
      <div className="space-y-6 max-w-7xl mx-auto font-sans">
        {/* Top Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-white/[0.08]">
          <div>
            <h1 className="text-xl font-bold tracking-tight text-[#F5F5F5]">
              {isDeptOfficer ? `Assigned ${activeDeptCode} Work Orders` : "Grievance Registry"}
            </h1>
            <p className="text-xs text-[#A1A1AA] mt-0.5">
              {isDeptOfficer
                ? `Active civic work orders assigned to ${activeDeptName} (${activeDeptCode}).`
                : "Municipal intake filtering, human verification, departmental dispatch & escalation tracking."}
            </p>
          </div>
          <div className="text-xs font-semibold text-[#A1A1AA] self-start sm:self-auto">
            {isDeptOfficer
              ? `Showing ${complaints.length} of ${total} assigned ${activeDeptCode} tasks`
              : `Showing ${complaints.length} of ${total} registered grievances`}
          </div>
        </div>

        {/* Search & Filter Bar */}
        <div className="bg-[#141722]/85 rounded-3xl border border-white/[0.08] p-5 shadow-xs space-y-4">
          <form onSubmit={handleSearchSubmit} className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <Search className="w-4 h-4 text-zinc-500 absolute left-4 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder={isDeptOfficer ? "Search by Complaint ID (e.g. JS-2026-00019), road location, description..." : "Search by Complaint ID (e.g. JS-2026-00019), citizen name, keywords..."}
                className="w-full pl-11 pr-4 py-2.5 bg-[#10131C] border border-white/[0.08] rounded-xl text-xs text-[#F5F5F5] placeholder-stone-400 focus:outline-none focus:ring-2 focus:ring-[#F36B21]/20 font-medium"
              />
            </div>
            <button
              type="submit"
              className="px-5 py-2.5 bg-[#F36B21] hover:bg-[#E05A10] text-white rounded-xl text-xs font-semibold flex items-center justify-center gap-2 cursor-pointer shadow-xs transition-colors"
            >
              <Search className="w-3.5 h-3.5" />
              <span>Search Records</span>
            </button>
            {(search || category || status || verificationStatus || departmentId) && (
              <button
                type="button"
                onClick={() => {
                  setSearch('')
                  setCategory('')
                  setStatus('')
                  setVerificationStatus('')
                  setDepartmentId('')
                  setPage(1)
                }}
                className="px-4 py-2.5 bg-[#10131C] hover:bg-white/[0.05] border border-white/[0.08] text-zinc-300 rounded-xl text-xs font-semibold cursor-pointer transition-colors"
              >
                Reset Filters
              </button>
            )}
          </form>

          {/* Filter Dropdowns */}
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-5 gap-3 pt-3 border-t border-white/[0.08]">
            <div>
              <label className="block text-[10px] font-bold uppercase text-[#A1A1AA] mb-1">Category</label>
              <select
                value={category}
                onChange={(e) => { setCategory(e.target.value); setPage(1) }}
                className="w-full py-1.5 px-2.5 bg-[#10131C] border border-white/[0.08] rounded-lg text-xs text-[#F5F5F5] font-medium"
              >
                <option value="">All Categories</option>
                <option value="Road Damage / Potholes">Road Damage</option>
                <option value="Sanitation / Garbage">Sanitation</option>
                <option value="Water Supply / Leakage">Water Supply</option>
                <option value="Drainage / Sewage">Drainage</option>
                <option value="Electrical / Streetlight">Streetlight</option>
              </select>
            </div>

            <div>
              <label className="block text-[10px] font-bold uppercase text-[#A1A1AA] mb-1">Civic Verification</label>
              <select
                value={verificationStatus}
                onChange={(e) => { setVerificationStatus(e.target.value); setPage(1) }}
                className="w-full py-1.5 px-2.5 bg-[#10131C] border border-white/[0.08] rounded-lg text-xs text-[#F5F5F5] font-medium"
              >
                <option value="">All Verification</option>
                <option value="pending">Pending Review</option>
                <option value="verified">Verified</option>
                <option value="rejected">Rejected</option>
                <option value="info_requested">Info Requested</option>
              </select>
            </div>

            <div>
              <label className="block text-[10px] font-bold uppercase text-[#A1A1AA] mb-1">Progress Status</label>
              <select
                value={status}
                onChange={(e) => { setStatus(e.target.value); setPage(1) }}
                className="w-full py-1.5 px-2.5 bg-[#10131C] border border-white/[0.08] rounded-lg text-xs text-[#F5F5F5] font-medium"
              >
                <option value="">All Statuses</option>
                <option value="Received">Received</option>
                <option value="Ready for Authority Officer">Ready for Officer</option>
                <option value="Verified">Verified</option>
                <option value="Awaiting Department Assignment">Awaiting Dept</option>
                <option value="Assigned">Assigned</option>
                <option value="In Progress">In Progress</option>
                <option value="Resolution Submitted">Resolution Submitted</option>
                <option value="Resolved">Resolved</option>
                <option value="Rejected">Rejected</option>
                <option value="Escalated">Escalated</option>
              </select>
            </div>

            <div>
              <label className="block text-[10px] font-bold uppercase text-[#A1A1AA] mb-1">Department</label>
              {isDeptOfficer ? (
                <div className="py-1.5 px-2.5 bg-[#10131C] border border-white/[0.08] rounded-lg text-xs text-[#F36B21] font-bold truncate">
                  {activeDeptCode} - {activeDeptName}
                </div>
              ) : (
                <select
                  value={departmentId}
                  onChange={(e) => { setDepartmentId(e.target.value); setPage(1) }}
                  className="w-full py-1.5 px-2.5 bg-[#10131C] border border-white/[0.08] rounded-lg text-xs text-[#F5F5F5] font-medium"
                >
                  <option value="">All Departments</option>
                  {departments.map((d) => (
                    <option key={d.id} value={d.id}>{d.code} - {d.name}</option>
                  ))}
                </select>
              )}
            </div>

            <div>
              <label className="block text-[10px] font-bold uppercase text-[#A1A1AA] mb-1">Sort Order</label>
              <select
                value={`${sortBy}_${sortDir}`}
                onChange={(e) => {
                  const [b, d] = e.target.value.split('_')
                  setSortBy(b)
                  setSortDir(d)
                }}
                className="w-full py-1.5 px-2.5 bg-[#10131C] border border-white/[0.08] rounded-lg text-xs text-[#F5F5F5] font-medium"
              >
                <option value="created_at_desc">Date (Newest First)</option>
                <option value="created_at_asc">Date (Oldest First)</option>
                <option value="complaint_id_desc">Complaint ID (Desc)</option>
                <option value="complaint_id_asc">Complaint ID (Asc)</option>
              </select>
            </div>
          </div>
        </div>

        {/* Complaints Table Container */}
        <div className="bg-[#141722]/85 rounded-3xl border border-white/[0.08] overflow-hidden shadow-xs">
          {loading ? (
            <div className="py-24 text-center">
              <RefreshCw className="w-8 h-8 text-[#F36B21] animate-spin mx-auto mb-3" />
              <p className="text-xs text-[#A1A1AA] font-medium">Loading civic grievance records...</p>
            </div>
          ) : complaints.length === 0 ? (
            <div className="py-24 text-center">
              <CheckCircle className="w-12 h-12 text-stone-300 mx-auto mb-3" />
              <h3 className="text-base font-bold text-[#F5F5F5]">No Complaints Match Current Criteria</h3>
              <p className="text-xs text-[#A1A1AA] mt-1">Try adjusting your search terms or filters.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="bg-[#10131C] border-b border-white/[0.08] text-[#A1A1AA] font-bold uppercase text-[10px] tracking-wider">
                    <th className="py-3 px-4">Complaint ID</th>
                    <th className="py-3 px-4">Category</th>
                    <th className="py-3 px-4">Citizen Description</th>
                    <th className="py-3 px-4">Verification</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4">Department</th>
                    <th className="py-3 px-4">Location Status</th>
                    <th className="py-3 px-4 text-center">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/[0.08]">
                  {complaints.map((c) => (
                    <tr key={c.complaint_id} className="hover:bg-[#10131C]/60 transition-colors group">
                      <td className="py-3.5 px-4 whitespace-nowrap">
                        <div className="flex items-center gap-1.5">
                          <Link
                            to={isDeptOfficer ? `/authority/work-orders/${c.complaint_id}?dept=${activeDeptId}` : `/authority/complaints/${c.complaint_id}`}
                            className="font-bold text-[#F5F5F5] group-hover:text-[#F36B21] transition-colors"
                          >
                            {c.complaint_id}
                          </Link>
                          {c.escalation_level > 0 && (
                            <Flame className="w-3.5 h-3.5 text-red-500" title={`Tier ${c.escalation_level} Escalated`} />
                          )}
                        </div>
                        <div className="flex items-center gap-1.5 text-[10px] text-zinc-500 mt-0.5">
                          <span>{c.created_at ? formatISTDateOnly(c.created_at) : ''}</span>
                          <span>•</span>
                          <span className="uppercase font-semibold">
                            {c.submission_channel}
                          </span>
                        </div>
                      </td>

                      <td className="py-3.5 px-4 whitespace-nowrap">
                        <span className="text-[#F5F5F5] font-semibold">{c.category}</span>
                        {c.google_maps_url ? (
                          <div className="flex items-center gap-1 text-[10px] text-emerald-400 font-medium mt-0.5">
                            <MapPin className="w-3 h-3 flex-shrink-0" />
                            <span>GPS Mapped</span>
                          </div>
                        ) : (
                          <div className="text-[10px] text-zinc-500 mt-0.5">
                            Approx / Manual
                          </div>
                        )}
                      </td>

                      <td className="py-3.5 px-4 max-w-xs">
                        <p className="text-[#A1A1AA] line-clamp-2 leading-relaxed">
                          {c.description}
                        </p>
                      </td>

                      <td className="py-3.5 px-4 whitespace-nowrap">
                        {getVerificationBadge(c.verification_status)}
                      </td>

                      <td className="py-3.5 px-4 whitespace-nowrap">
                        {getAdminStatusBadge(c.admin_status)}
                      </td>

                      <td className="py-3.5 px-4 whitespace-nowrap">
                        {c.department ? (
                          <div>
                            <span className="font-bold text-[#F36B21]">{c.department.code}</span>
                            <span className="block text-[10px] text-[#A1A1AA] truncate max-w-[120px]">
                              {c.department.name}
                            </span>
                          </div>
                        ) : (
                          <span className="text-[10px] text-zinc-500 italic">Unassigned</span>
                        )}
                      </td>

                      <td className="py-3.5 px-4 whitespace-nowrap">
                        {c.latitude && c.longitude ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30" title={`${c.latitude}, ${c.longitude}`}>
                            <MapPin className="w-3 h-3 flex-shrink-0" />
                            <span>GPS Grounded</span>
                          </span>
                        ) : c.google_maps_url ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-sky-500/10 text-sky-400 border border-sky-500/30">
                            <MapPin className="w-3 h-3 flex-shrink-0" />
                            <span>Address Only</span>
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/30">
                            <span>Clarification Req</span>
                          </span>
                        )}
                      </td>

                      <td className="py-3.5 px-4 text-center whitespace-nowrap">
                        <Link
                          to={isDeptOfficer ? `/authority/work-orders/${c.complaint_id}?dept=${activeDeptId}` : `/authority/complaints/${c.complaint_id}`}
                          className="px-3 py-1 rounded-lg bg-white/[0.05] hover:bg-white/[0.1] text-[#F5F5F5] font-semibold text-[11px] transition-colors"
                        >
                          Inspect
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination */}
          <div className="p-4 border-t border-white/[0.08] flex items-center justify-between text-xs text-[#A1A1AA] bg-[#10131C]">
            <span>Page {page} of {totalPages}</span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage(Math.max(1, page - 1))}
                disabled={page <= 1}
                className="px-3 py-1.5 rounded-lg border border-white/[0.08] bg-[#141722]/85 text-zinc-300 hover:bg-white/[0.03] disabled:opacity-40 cursor-pointer font-semibold"
              >
                Previous
              </button>
              <button
                onClick={() => setPage(Math.min(totalPages, page + 1))}
                disabled={page >= totalPages}
                className="px-3 py-1.5 rounded-lg border border-white/[0.08] bg-[#141722]/85 text-zinc-300 hover:bg-white/[0.03] disabled:opacity-40 cursor-pointer font-semibold"
              >
                Next
              </button>
            </div>
          </div>
        </div>
      </div>
    </AuthorityLayout>
  )
}
