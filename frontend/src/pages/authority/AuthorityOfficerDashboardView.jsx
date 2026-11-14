import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  Shield, CheckCircle2, XCircle, Clock, Building2, Flame,
  RefreshCw, ChevronRight, Filter, FileText, AlertCircle,
  MapPin, Wrench, ArrowRight, UserCheck, Calendar, AlertTriangle,
  RotateCcw, Send, Check, ShieldCheck
} from 'lucide-react'
import { formatToIST, formatISTDateOnly } from '../../utils/dateTime'
import { useAuth } from '../../context/AuthContext'

const DEPARTMENTS_LIST = [
  { id: 1, code: 'RPW', name: 'Roads & Public Works', sla: 7, sla_days: 7 },
  { id: 2, code: 'SWM', name: 'Sanitation & Waste Management', sla: 3, sla_days: 3 },
  { id: 3, code: 'WSD', name: 'Water Supply & Sewerage', sla: 5, sla_days: 5 },
  { id: 4, code: 'DRN', name: 'Storm Water Drainage', sla: 4, sla_days: 4 },
  { id: 5, code: 'ESM', name: 'Electrical & Street Lighting', sla: 2, sla_days: 2 },
  { id: 6, code: 'PID', name: 'Public Infrastructure & Parks', sla: 10, sla_days: 10 }
]

export default function AuthorityOfficerDashboardView({ data, loading, onRefresh }) {
  const { authFetch } = useAuth()
  const [activeTab, setActiveTab] = useState('queue') // 'queue' | 'dispatch' | 'monitoring' | 'resolution'
  const [selectedComplaint, setSelectedComplaint] = useState(null)
  const [decisionModalOpen, setDecisionModalOpen] = useState(false)
  const [rejectionModalOpen, setRejectionModalOpen] = useState(false)
  const [dispatchModalOpen, setDispatchModalOpen] = useState(false)
  const [returnModalOpen, setReturnModalOpen] = useState(false)

  // Form states
  const [rejectionReason, setRejectionReason] = useState('')
  const [returnNotes, setReturnNotes] = useState('')
  const [departmentsList, setDepartmentsList] = useState(DEPARTMENTS_LIST)
  const [selectedDeptId, setSelectedDeptId] = useState(1)
  const [selectedOfficerId, setSelectedOfficerId] = useState('')
  const [assignedPriority, setAssignedPriority] = useState('High')
  const [assignmentDate, setAssignmentDate] = useState(() => new Date().toISOString().split('T')[0])
  const [expectedDays, setExpectedDays] = useState(7)
  const [expectedCompletionDate, setExpectedCompletionDate] = useState('')
  const [assignmentInstructions, setAssignmentInstructions] = useState('')
  const [dispatchConfirmed, setDispatchConfirmed] = useState(false)
  const [validationError, setValidationError] = useState(null)
  const [actionLoading, setActionLoading] = useState(false)
  const [actionSuccess, setActionSuccess] = useState(null)
  const [actionError, setActionError] = useState(null)

  // Fetch live departments with users
  useEffect(() => {
    const loadDepartments = async () => {
      try {
        const res = await authFetch('http://127.0.0.1:8000/api/authority/departments')
        if (res.ok) {
          const json = await res.json()
          if (json.departments && json.departments.length > 0) {
            setDepartmentsList(json.departments)
          }
        }
      } catch (err) {
        console.warn('Using default departments list:', err)
      }
    }
    loadDepartments()
  }, [])

  // Calculate expected completion date when assignmentDate or expectedDays changes
  useEffect(() => {
    if (assignmentDate) {
      try {
        const d = new Date(assignmentDate)
        d.setDate(d.getDate() + Number(expectedDays || 7))
        setExpectedCompletionDate(d.toISOString().split('T')[0])
      } catch {
        // fallback
      }
    }
  }, [assignmentDate, expectedDays])

  const kpis = data?.kpis || {}
  const complaints = data?.complaints || []
  const nowStr = formatISTDateOnly(new Date())

  // KPI calculations
  const awaitingDecision = kpis.awaiting_decision ?? complaints.filter((c) => c.admin_status === 'Ready for Authority Officer' && c.verification_status === 'pending' && c.latitude != null && c.longitude != null).length
  const acceptedCount = kpis.accepted_complaints ?? complaints.filter((c) => c.verification_status === 'verified').length
  const awaitingAssignment = kpis.awaiting_department_assignment ?? complaints.filter((c) => c.admin_status === 'Awaiting Department Assignment').length
  const activeWorkOrders = kpis.active_work_orders ?? complaints.filter((c) => ['Assigned', 'In Progress', 'Under Inspection', 'Resolution Submitted'].includes(c.admin_status)).length
  const overdueCount = kpis.escalated_complaints ?? complaints.filter((c) => (c.escalation_level || 0) > 0 || c.admin_status === 'Escalated').length

  // Action 1: Accept Complaint (Civic Decision)
  const handleAcceptComplaint = async (complaint) => {
    setActionLoading(true)
    setActionSuccess(null)
    setActionError(null)
    try {
      const res = await authFetch(`http://127.0.0.1:8000/api/authority/complaints/${complaint.complaint_id}/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ notes: 'Civic verification approved for municipal departmental action.' })
      })
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}))
        throw new Error(errJson.detail || 'Verification failed.')
      }
      setActionSuccess(`Complaint ${complaint.complaint_id} verified and accepted for dispatch.`)
      // Open dispatch modal directly
      setSelectedComplaint(complaint)
      setDispatchModalOpen(true)
      if (onRefresh) onRefresh()
    } catch (err) {
      setActionError(err.message || 'Error accepting complaint.')
    } finally {
      setActionLoading(false)
    }
  }

  // Action 2: Reject Complaint with mandatory reason
  const handleRejectComplaint = async (e) => {
    e.preventDefault()
    if (!rejectionReason.trim() || !selectedComplaint) return
    setActionLoading(true)
    setActionSuccess(null)
    setActionError(null)
    try {
      const res = await authFetch(`http://127.0.0.1:8000/api/authority/complaints/${selectedComplaint.complaint_id}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: rejectionReason.trim() })
      })
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}))
        throw new Error(errJson.detail || 'Rejection failed.')
      }
      setActionSuccess(`Complaint ${selectedComplaint.complaint_id} rejected with recorded reason.`)
      setRejectionModalOpen(false)
      setRejectionReason('')
      if (onRefresh) onRefresh()
    } catch (err) {
      setActionError(err.message || 'Error rejecting complaint.')
    } finally {
      setActionLoading(false)
    }
  }

  // Action 3: Dispatch Work Order to Department
  const handleDispatchWorkOrder = async (e) => {
    e.preventDefault()
    if (!selectedComplaint) return
    setValidationError(null)

    // Validate that officer belongs to selected department
    const currentDept = departmentsList.find((d) => d.id === Number(selectedDeptId))
    const availableOfficers = currentDept?.users || []
    if (selectedOfficerId) {
      const officerValid = availableOfficers.some((u) => u.id === Number(selectedOfficerId))
      if (!officerValid) {
        setValidationError(`Selected officer does not belong to ${currentDept?.name || 'this department'}.`)
        return
      }
    }

    if (!dispatchConfirmed) {
      setValidationError('Please review and check the dispatch confirmation before issuing the work order.')
      return
    }

    setActionLoading(true)
    setActionSuccess(null)
    setActionError(null)
    try {
      const res = await authFetch(`http://127.0.0.1:8000/api/authority/complaints/${selectedComplaint.complaint_id}/assign`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          department_id: Number(selectedDeptId),
          assigned_to_user_id: selectedOfficerId ? Number(selectedOfficerId) : null,
          priority: assignedPriority,
          assignment_date: assignmentDate,
          expected_completion_date: expectedCompletionDate,
          expected_completion_days: Number(expectedDays),
          notes: assignmentInstructions.trim()
        })
      })
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}))
        throw new Error(errJson.detail || 'Dispatch failed.')
      }
      const deptObj = departmentsList.find((d) => d.id === Number(selectedDeptId))
      setActionSuccess(`Work order for ${selectedComplaint.complaint_id} dispatched to ${deptObj?.name || 'Department'}.`)
      setDispatchModalOpen(false)
      setAssignmentInstructions('')
      setDispatchConfirmed(false)
      setSelectedOfficerId('')
      setValidationError(null)
      if (onRefresh) onRefresh()
    } catch (err) {
      setActionError(err.message || 'Error dispatching work order.')
    } finally {
      setActionLoading(false)
    }
  }

  // Action 4: Approve Resolution and Close Complaint
  const handleApproveResolution = async (complaintId) => {
    setActionLoading(true)
    setActionSuccess(null)
    setActionError(null)
    try {
      const res = await authFetch(`http://127.0.0.1:8000/api/authority/complaints/${complaintId}/status`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          status: 'Resolved',
          notes: 'Authority Officer reviewed field evidence and approved final closure.'
        })
      })
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}))
        throw new Error(errJson.detail || 'Resolution approval failed.')
      }
      setActionSuccess(`Complaint ${complaintId} successfully closed and marked Resolved.`)
      if (onRefresh) onRefresh()
    } catch (err) {
      setActionError(err.message || 'Error approving resolution.')
    } finally {
      setActionLoading(false)
    }
  }

  // Action 5: Return Work for Correction
  const handleReturnCorrection = async (e) => {
    e.preventDefault()
    if (!returnNotes.trim() || !selectedComplaint) return
    setActionLoading(true)
    setActionSuccess(null)
    setActionError(null)
    try {
      const res = await authFetch(`http://127.0.0.1:8000/api/authority/complaints/${selectedComplaint.complaint_id}/return-correction`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ correction_notes: returnNotes.trim() })
      })
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}))
        throw new Error(errJson.detail || 'Return for correction failed.')
      }
      setActionSuccess(`Work order for ${selectedComplaint.complaint_id} returned to department for correction.`)
      setReturnModalOpen(false)
      setReturnNotes('')
      if (onRefresh) onRefresh()
    } catch (err) {
      setActionError(err.message || 'Error returning work.')
    } finally {
      setActionLoading(false)
    }
  }

  return (
    <div className="space-y-8 max-w-7xl mx-auto font-sans">
      {/* 1. Hero Section (COSMO Warm Minimal Aesthetic) */}
      <div className="relative rounded-3xl bg-[#141722]/85 border border-white/[0.08] shadow-[0_4px_24px_rgba(24,24,27,0.04)] overflow-hidden">
        {/* Subtle warm gradients */}
        <div className="absolute top-0 right-1/4 w-96 h-96 bg-gradient-to-b from-[#F7E7D4]/60 to-transparent rounded-full blur-[100px] pointer-events-none" />

        <div className="grid grid-cols-1 lg:grid-cols-12 items-center min-h-[320px] relative z-10">
          {/* Left Hero Content */}
          <div className="lg:col-span-7 p-6 sm:p-10 flex flex-col justify-between">
            <div>
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#10131C] border border-white/[0.08] text-[11px] font-semibold text-[#A1A1AA] mb-4 shadow-xs">
                <span className="w-2 h-2 rounded-full bg-[#138A4B] animate-pulse" />
                <span className="uppercase tracking-wider">Role 2 • Decision & Department Assignment</span>
                <span>•</span>
                <span className="text-[#F36B21]">{nowStr}</span>
              </div>

              <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-[#F5F5F5] leading-tight">
                Civic Decision & Dispatch Centre
              </h1>

              <p className="text-sm text-[#A1A1AA] mt-2.5 max-w-lg leading-relaxed">
                Review prepared grievances from Admin, make authoritative civic verification decisions, dispatch work orders to responsible municipal divisions with deadlines, and verify final repair completion.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3 mt-6 pt-6 border-t border-white/[0.08]">
              <Link
                to="/authority/verification-queue"
                className="px-5 py-2.5 rounded-xl bg-[#F36B21] hover:bg-[#E05A10] text-white font-semibold text-xs flex items-center gap-2 shadow-sm transition-all"
              >
                <span>Assignment Queue ({awaitingDecision})</span>
                <ChevronRight className="w-4 h-4" />
              </Link>
              <Link
                to="/authority/departments"
                className="px-4 py-2.5 rounded-xl bg-[#141722]/85 hover:bg-white/[0.03] border border-white/[0.08] text-[#F5F5F5] font-semibold text-xs flex items-center gap-2 shadow-xs transition-all"
              >
                <Building2 className="w-3.5 h-3.5 text-[#0284C7]" />
                <span>Department Workload</span>
              </Link>
              <Link
                to="/authority/escalations"
                className="px-4 py-2.5 rounded-xl bg-[#141722]/85 hover:bg-white/[0.03] border border-white/[0.08] text-[#F5F5F5] font-semibold text-xs flex items-center gap-2 shadow-xs transition-all"
              >
                <Flame className="w-3.5 h-3.5 text-[#DC2626]" />
                <span>Escalations ({overdueCount})</span>
              </Link>
              <button
                onClick={onRefresh}
                className="px-3.5 py-2.5 rounded-xl bg-[#10131C] hover:bg-[#F3EFE7] border border-white/[0.08] text-[#A1A1AA] hover:text-[#F5F5F5] text-xs font-semibold flex items-center gap-1.5 transition-all cursor-pointer"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
                <span>Sync</span>
              </button>
            </div>
          </div>

          {/* Right Hero Image (Gemini-Generated Indian Municipal Authority Officer in warm morning light) */}
          <div className="lg:col-span-5 h-72 lg:h-full relative overflow-hidden flex items-end justify-center lg:justify-end">
            <div className="relative w-full h-full min-h-[300px]">
              <img
                src="/assets/authority_hero.jpg"
                alt="Authority Officer"
                className="w-full h-full object-cover object-center"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-[#141722] via-transparent to-transparent lg:bg-gradient-to-r lg:from-[#141722] lg:via-transparent lg:to-transparent" />
            </div>
          </div>
        </div>
      </div>

      {/* Action Feedback Notifications */}
      {actionSuccess && (
        <div className="p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs flex items-center justify-between shadow-xs">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
            <span className="font-medium">{actionSuccess}</span>
          </div>
          <button onClick={() => setActionSuccess(null)} className="text-emerald-400 hover:underline text-[11px]">Dismiss</button>
        </div>
      )}
      {actionError && (
        <div className="p-4 rounded-2xl bg-red-500/10 border border-red-500/30 text-red-400 text-xs flex items-center justify-between shadow-xs">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0" />
            <span className="font-medium">{actionError}</span>
          </div>
          <button onClick={() => setActionError(null)} className="text-red-400 hover:underline text-[11px]">Dismiss</button>
        </div>
      )}

      {/* 2. Primary 5 KPI Cards (COSMO Minimal Metrics) */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        {/* Awaiting Decision */}
        <div className="p-5 rounded-2xl bg-[#141722]/85 border border-white/[0.08] shadow-xs">
          <div className="flex items-center justify-between text-zinc-500 mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-amber-400">Awaiting Decision</span>
            <Clock className="w-4 h-4 text-amber-500" />
          </div>
          <div className="text-3xl font-extrabold text-[#F5F5F5] tracking-tight">{awaitingDecision}</div>
          <div className="text-[11px] text-[#A1A1AA] mt-1 font-medium">Prepared by Admin</div>
        </div>

        {/* Accepted Complaints */}
        <div className="p-5 rounded-2xl bg-[#141722]/85 border border-white/[0.08] shadow-xs">
          <div className="flex items-center justify-between text-zinc-500 mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-400">Accepted</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-500" />
          </div>
          <div className="text-3xl font-extrabold text-[#F5F5F5] tracking-tight">{acceptedCount}</div>
          <div className="text-[11px] text-[#A1A1AA] mt-1 font-medium">Civic verification approved</div>
        </div>

        {/* Awaiting Department Assignment */}
        <div className="p-5 rounded-2xl bg-[#141722]/85 border border-white/[0.08] shadow-xs">
          <div className="flex items-center justify-between text-zinc-500 mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-sky-400">Awaiting Dispatch</span>
            <Building2 className="w-4 h-4 text-sky-500" />
          </div>
          <div className="text-3xl font-extrabold text-[#F5F5F5] tracking-tight">{awaitingAssignment}</div>
          <div className="text-[11px] text-[#A1A1AA] mt-1 font-medium">Ready for department dispatch</div>
        </div>

        {/* Active Work Orders */}
        <div className="p-5 rounded-2xl bg-[#141722]/85 border border-white/[0.08] shadow-xs">
          <div className="flex items-center justify-between text-zinc-500 mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-zinc-300">Active Work Orders</span>
            <Wrench className="w-4 h-4 text-[#A1A1AA]" />
          </div>
          <div className="text-3xl font-extrabold text-[#F5F5F5] tracking-tight">{activeWorkOrders}</div>
          <div className="text-[11px] text-[#A1A1AA] mt-1 font-medium">Assigned across 6 departments</div>
        </div>

        {/* Overdue / Escalated */}
        <div className="p-5 rounded-2xl bg-[#141722]/85 border border-white/[0.08] shadow-xs col-span-2 lg:col-span-1">
          <div className="flex items-center justify-between text-zinc-500 mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-red-400">Overdue / Escalated</span>
            <Flame className="w-4 h-4 text-red-500" />
          </div>
          <div className="text-3xl font-extrabold text-[#DC2626] tracking-tight">{overdueCount}</div>
          <div className="text-[11px] text-[#A1A1AA] mt-1 font-medium">Exceeding SLA limits</div>
        </div>
      </div>

      {/* 3. Operational Workspaces Tabs (COSMO Segmented Pill Controls) */}
      <div className="flex items-center justify-between flex-wrap gap-3 pb-2 border-b border-white/[0.08]">
        <div className="inline-flex p-1 rounded-full bg-[#10131C] border border-white/[0.08]">
          <button
            onClick={() => setActiveTab('queue')}
            className={`px-4 py-1.5 rounded-full text-xs font-semibold transition-all cursor-pointer ${
              activeTab === 'queue' ? 'bg-[#F36B21] text-white shadow-xs' : 'text-[#A1A1AA] hover:text-[#F5F5F5]'
            }`}
          >
            Assignment Queue ({awaitingDecision})
          </button>
          <button
            onClick={() => setActiveTab('dispatch')}
            className={`px-4 py-1.5 rounded-full text-xs font-semibold transition-all cursor-pointer ${
              activeTab === 'dispatch' ? 'bg-[#F36B21] text-white shadow-xs' : 'text-[#A1A1AA] hover:text-[#F5F5F5]'
            }`}
          >
            Department Dispatch ({awaitingAssignment})
          </button>
          <button
            onClick={() => setActiveTab('monitoring')}
            className={`px-4 py-1.5 rounded-full text-xs font-semibold transition-all cursor-pointer ${
              activeTab === 'monitoring' ? 'bg-[#F36B21] text-white shadow-xs' : 'text-[#A1A1AA] hover:text-[#F5F5F5]'
            }`}
          >
            Work Monitoring ({activeWorkOrders})
          </button>
          <button
            onClick={() => setActiveTab('resolution')}
            className={`px-4 py-1.5 rounded-full text-xs font-semibold transition-all cursor-pointer ${
              activeTab === 'resolution' ? 'bg-[#F36B21] text-white shadow-xs' : 'text-[#A1A1AA] hover:text-[#F5F5F5]'
            }`}
          >
            Resolution Review
          </button>
        </div>

        <span className="text-xs text-[#A1A1AA] font-medium">
          Authoritative civic decisions & departmental assignment
        </span>
      </div>

      {/* 4. Tab 1: Assignment Queue (Prepared Complaints Awaiting Officer Decision) */}
      {activeTab === 'queue' && (
        <div className="bg-[#141722]/85 rounded-3xl border border-white/[0.08] shadow-xs overflow-hidden">
          <div className="p-6 border-b border-white/[0.08] flex items-center justify-between flex-wrap gap-4">
            <div>
              <h2 className="text-base font-bold text-[#F5F5F5]">Prepared Grievances Awaiting Civic Decision</h2>
              <p className="text-xs text-[#A1A1AA] mt-0.5">
                Review complaints prepared by Admin. Accept for departmental dispatch or reject with recorded justification.
              </p>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-[#10131C] border-b border-white/[0.08] text-[#A1A1AA] font-bold uppercase tracking-wider text-[10px]">
                  <th className="py-3.5 px-5">ID & Category</th>
                  <th className="py-3.5 px-5">Description</th>
                  <th className="py-3.5 px-5">Location</th>
                  <th className="py-3.5 px-5">Preparation Status</th>
                  <th className="py-3.5 px-5">Current Decision</th>
                  <th className="py-3.5 px-5 text-right">Civic Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.08]">
                {complaints
                  .filter((c) => c.admin_status === 'Ready for Authority Officer' && c.verification_status === 'pending' && c.latitude != null && c.longitude != null)
                  .slice(0, 10)
                  .map((c) => (
                    <tr key={c.id} className="hover:bg-[#10131C]/60 transition-colors">
                      <td className="py-3.5 px-5">
                        <Link
                          to={`/authority/complaints/${c.complaint_id}`}
                          className="font-bold text-[#F5F5F5] hover:text-[#F36B21] transition-colors"
                        >
                          {c.complaint_id}
                        </Link>
                        <div className="font-semibold text-[#F5F5F5] text-[11px] mt-0.5">{c.category}</div>
                      </td>

                      <td className="py-3.5 px-5 max-w-xs">
                        <div className="text-[#A1A1AA] truncate text-[11px]" title={c.description}>
                          {c.description}
                        </div>
                      </td>

                      <td className="py-3.5 px-5 whitespace-nowrap">
                        <div className="flex items-center gap-1 text-[#F5F5F5] font-medium">
                          <MapPin className="w-3.5 h-3.5 text-zinc-500" />
                          <span>{c.latitude ? `${c.latitude.toFixed(4)}, ${c.longitude.toFixed(4)}` : 'Location Pending'}</span>
                        </div>
                      </td>

                      <td className="py-3.5 px-5 whitespace-nowrap">
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full font-bold text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                          <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                          <span>Ready for Officer</span>
                        </span>
                      </td>

                      <td className="py-3.5 px-5 whitespace-nowrap">
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/30">
                          <Clock className="w-3 h-3" />
                          <span>Awaiting Decision</span>
                        </span>
                      </td>

                      <td className="py-3.5 px-5 text-right whitespace-nowrap">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => handleAcceptComplaint(c)}
                            disabled={actionLoading}
                            className="px-3 py-1 rounded-lg bg-[#138A4B] hover:bg-[#16A34A] text-white font-semibold text-[11px] transition-colors flex items-center gap-1 shadow-xs cursor-pointer"
                          >
                            <Check className="w-3 h-3" />
                            <span>Accept</span>
                          </button>
                          <button
                            onClick={() => {
                              setSelectedComplaint(c)
                              setRejectionModalOpen(true)
                            }}
                            disabled={actionLoading}
                            className="px-2.5 py-1 rounded-lg bg-red-500/10 hover:bg-red-100 text-red-400 border border-red-500/30 font-semibold text-[11px] transition-colors cursor-pointer"
                          >
                            Reject
                          </button>
                          <Link
                            to={`/authority/complaints/${c.complaint_id}`}
                            className="px-2.5 py-1 rounded-lg bg-white/[0.05] hover:bg-white/[0.1] text-zinc-300 font-semibold text-[11px] transition-colors"
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
        </div>
      )}

      {/* 5. Tab 2: Department Dispatch Workspace */}
      {activeTab === 'dispatch' && (
        <div className="bg-[#141722]/85 rounded-3xl border border-white/[0.08] p-7 shadow-xs space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-bold text-[#F5F5F5]">Municipal Department Dispatch Queue</h2>
              <p className="text-xs text-[#A1A1AA] mt-1">
                Assign accepted civic complaints to the responsible municipal department, set deadlines, and dispatch work orders.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {complaints
              .filter((c) => c.verification_status === 'verified' && !c.department)
              .map((c) => (
                <div key={c.id} className="p-5 rounded-2xl bg-[#10131C] border border-white/[0.08] flex flex-col justify-between space-y-4">
                  <div>
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-sm text-[#F5F5F5]">{c.complaint_id}</span>
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                        Accepted
                      </span>
                    </div>
                    <div className="font-semibold text-xs text-[#F5F5F5] mt-1">{c.category}</div>
                    <p className="text-xs text-[#A1A1AA] mt-1 line-clamp-2">{c.description}</p>
                  </div>

                  <div className="pt-3 border-t border-white/[0.08] flex items-center justify-between">
                    <span className="text-[11px] text-[#A1A1AA]">{c.latitude ? 'Location Confirmed' : 'No GPS'}</span>
                    <button
                      onClick={() => {
                        setSelectedComplaint(c)
                        setDispatchModalOpen(true)
                      }}
                      className="px-3 py-1.5 rounded-xl bg-[#F36B21] hover:bg-[#E05A10] text-white font-semibold text-xs flex items-center gap-1.5 shadow-xs transition-colors cursor-pointer"
                    >
                      <span>Dispatch</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* 6. Tab 3: Work Monitoring & Deadlines */}
      {activeTab === 'monitoring' && (
        <div className="bg-[#141722]/85 rounded-3xl border border-white/[0.08] p-7 shadow-xs space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-bold text-[#F5F5F5]">Department Work Monitoring & Deadlines</h2>
              <p className="text-xs text-[#A1A1AA] mt-1">
                Track active work orders across departments, monitor approaching SLA deadlines, and escalate delayed work.
              </p>
            </div>
            <Link
              to="/authority/escalations"
              className="text-xs font-bold text-[#DC2626] hover:underline flex items-center gap-1"
            >
              <span>View Escalations</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-[#10131C] border-b border-white/[0.08] text-[#A1A1AA] font-bold uppercase tracking-wider text-[10px]">
                  <th className="py-3 px-4">Complaint ID</th>
                  <th className="py-3 px-4">Department</th>
                  <th className="py-3 px-4">Work Status</th>
                  <th className="py-3 px-4">Assignment Notes</th>
                  <th className="py-3 px-4 text-right">Inspect</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.08]">
                {complaints
                  .filter((c) => c.department)
                  .slice(0, 8)
                  .map((c) => (
                    <tr key={c.id} className="hover:bg-[#10131C]/60 transition-colors">
                      <td className="py-3 px-4 font-bold text-[#F5F5F5]">{c.complaint_id}</td>
                      <td className="py-3 px-4 font-semibold text-[#F5F5F5]">{c.department?.name || 'Department'}</td>
                      <td className="py-3 px-4">
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-sky-500/10 text-sky-400 border border-sky-500/30">
                          {c.admin_status || 'Assigned'}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-[#A1A1AA] truncate max-w-xs">{c.assignment_notes || 'Standard SLA'}</td>
                      <td className="py-3 px-4 text-right">
                        <Link to={`/authority/complaints/${c.complaint_id}`} className="text-zinc-300 font-semibold hover:underline">
                          View
                        </Link>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 7. Tab 4: Resolution Review & Final Closure */}
      {activeTab === 'resolution' && (
        <div className="bg-[#141722]/85 rounded-3xl border border-white/[0.08] p-7 shadow-xs space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-bold text-[#F5F5F5]">Department Resolution Evidence Review</h2>
              <p className="text-xs text-[#A1A1AA] mt-1">
                Review completed repair evidence submitted by department officers. Approve final closure or return for correction.
              </p>
            </div>
          </div>

          <div className="space-y-4">
            {complaints
              .filter((c) => c.admin_status === 'Resolution Submitted' || c.admin_status === 'In Progress')
              .slice(0, 5)
              .map((c) => (
                <div key={c.id} className="p-5 rounded-2xl bg-[#10131C] border border-white/[0.08] flex items-center justify-between flex-wrap gap-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-sm text-[#F5F5F5]">{c.complaint_id}</span>
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-purple-500/10 text-purple-400 border border-purple-500/30">
                        {c.admin_status}
                      </span>
                    </div>
                    <div className="font-semibold text-xs text-[#F5F5F5] mt-1">{c.category} • {c.department?.name}</div>
                    <p className="text-xs text-[#A1A1AA] mt-0.5">{c.description}</p>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleApproveResolution(c.complaint_id)}
                      disabled={actionLoading}
                      className="px-3.5 py-1.5 rounded-xl bg-[#138A4B] hover:bg-[#16A34A] text-white font-semibold text-xs flex items-center gap-1.5 shadow-xs cursor-pointer"
                    >
                      <Check className="w-3.5 h-3.5" />
                      <span>Approve & Close</span>
                    </button>
                    <button
                      onClick={() => {
                        setSelectedComplaint(c)
                        setReturnModalOpen(true)
                      }}
                      disabled={actionLoading}
                      className="px-3.5 py-1.5 rounded-xl bg-[#141722]/85 hover:bg-white/[0.03] border border-white/[0.08] text-[#F5F5F5] font-semibold text-xs flex items-center gap-1.5 shadow-xs cursor-pointer"
                    >
                      <RotateCcw className="w-3.5 h-3.5 text-amber-600" />
                      <span>Return for Correction</span>
                    </button>
                  </div>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* MODAL 1: Reject Complaint with mandatory reason */}
      {rejectionModalOpen && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#141722]/85 rounded-3xl p-6 sm:p-7 max-w-md w-full border border-white/[0.08] shadow-2xl space-y-4">
            <div>
              <h3 className="text-base font-bold text-[#F5F5F5]">Reject Complaint</h3>
              <p className="text-xs text-[#A1A1AA] mt-1">
                Provide a clear mandatory justification for rejecting complaint {selectedComplaint?.complaint_id}.
              </p>
            </div>

            <form onSubmit={handleRejectComplaint} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-zinc-300 mb-1">
                  Rejection Reason (Mandatory)
                </label>
                <textarea
                  required
                  rows={3}
                  value={rejectionReason}
                  onChange={(e) => setRejectionReason(e.target.value)}
                  placeholder="e.g. Duplicate report already being serviced under PO #8491, or issue does not fall within municipal jurisdiction."
                  className="w-full p-3 rounded-xl bg-[#10131C] border border-white/[0.08] text-xs text-[#F5F5F5] focus:outline-none focus:ring-2 focus:ring-[#DC2626]/20 focus:border-[#DC2626]"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setRejectionModalOpen(false)}
                  className="px-4 py-2 rounded-xl text-[#A1A1AA] text-xs font-semibold hover:bg-white/[0.05] cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-4 py-2 rounded-xl bg-[#DC2626] hover:bg-[#B91C1C] text-white text-xs font-semibold shadow-xs cursor-pointer"
                >
                  Confirm Rejection
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 2: Department Dispatch Workspace */}
      {dispatchModalOpen && (() => {
        const currentDept = departmentsList.find((d) => d.id === Number(selectedDeptId)) || departmentsList[0]
        const availableOfficers = currentDept?.users || []
        const selectedOfficer = availableOfficers.find((u) => u.id === Number(selectedOfficerId))

        return (
          <div className="fixed inset-0 bg-black/60 backdrop-blur-md z-50 flex items-center justify-center p-4">
            <div className="bg-[#141722]/95 rounded-3xl p-6 sm:p-7 max-w-lg w-full border border-white/[0.1] shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
              <div className="flex items-start justify-between border-b border-white/[0.08] pb-3">
                <div>
                  <h3 className="text-base font-bold text-[#F5F5F5] flex items-center gap-2">
                    <Send className="w-4 h-4 text-[#F36B21]" />
                    <span>Dispatch Municipal Work Order</span>
                  </h3>
                  <p className="text-xs text-[#A1A1AA] mt-1">
                    Grievance: <strong className="text-[#F5F5F5]">{selectedComplaint?.complaint_id}</strong> • {selectedComplaint?.category}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setDispatchModalOpen(false)
                    setValidationError(null)
                    setDispatchConfirmed(false)
                  }}
                  className="p-1 rounded-lg text-[#A1A1AA] hover:text-[#F5F5F5] hover:bg-white/[0.05]"
                >
                  <XCircle className="w-5 h-5" />
                </button>
              </div>

              {validationError && (
                <div className="p-3 rounded-xl bg-red-500/15 border border-red-500/30 text-red-300 text-xs flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 flex-shrink-0" />
                  <span>{validationError}</span>
                </div>
              )}

              <form onSubmit={handleDispatchWorkOrder} className="space-y-4">
                {/* 1. Department Selection */}
                <div>
                  <label className="block text-xs font-semibold text-zinc-300 mb-1 flex items-center gap-1.5">
                    <Building2 className="w-3.5 h-3.5 text-[#F36B21]" />
                    <span>Responsible Municipal Department</span>
                  </label>
                  <select
                    value={selectedDeptId}
                    onChange={(e) => {
                      const newDeptId = Number(e.target.value)
                      setSelectedDeptId(newDeptId)
                      setSelectedOfficerId('')
                      setValidationError(null)
                      const dept = departmentsList.find((d) => d.id === newDeptId)
                      if (dept) setExpectedDays(dept.sla_days || dept.sla || 7)
                    }}
                    className="w-full p-2.5 rounded-xl bg-[#10131C] border border-white/[0.08] text-xs text-[#F5F5F5] focus:outline-none focus:ring-2 focus:ring-[#F36B21]/20 font-semibold cursor-pointer"
                  >
                    {departmentsList.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.code} — {d.name} (SLA: {d.sla_days || d.sla || 7} days)
                      </option>
                    ))}
                  </select>
                </div>

                {/* 2. Responsible Department Officer Selection (Filtered & Validated) */}
                <div>
                  <label className="block text-xs font-semibold text-zinc-300 mb-1 flex items-center justify-between">
                    <span className="flex items-center gap-1.5">
                      <UserCheck className="w-3.5 h-3.5 text-[#38BDF8]" />
                      <span>Responsible Department Officer</span>
                    </span>
                    <span className="text-[10px] text-[#A1A1AA]">
                      {availableOfficers.length} officer(s) in {currentDept?.code}
                    </span>
                  </label>
                  <select
                    value={selectedOfficerId}
                    onChange={(e) => {
                      setSelectedOfficerId(e.target.value)
                      setValidationError(null)
                    }}
                    className="w-full p-2.5 rounded-xl bg-[#10131C] border border-white/[0.08] text-xs text-[#F5F5F5] focus:outline-none focus:ring-2 focus:ring-[#F36B21]/20 cursor-pointer"
                  >
                    <option value="">
                      Auto-Assign to Division Head ({currentDept?.head_name || 'Department Pool'})
                    </option>
                    {availableOfficers.map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.full_name} ({u.role ? u.role.replace('_', ' ') : 'Officer'})
                      </option>
                    ))}
                  </select>
                </div>

                {/* 3. Priority & Expected Days */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-semibold text-zinc-300 mb-1">Priority</label>
                    <select
                      value={assignedPriority}
                      onChange={(e) => setAssignedPriority(e.target.value)}
                      className="w-full p-2.5 rounded-xl bg-[#10131C] border border-white/[0.08] text-xs text-[#F5F5F5] cursor-pointer"
                    >
                      <option value="Critical">Critical (Immediate Dispatch)</option>
                      <option value="High">High (48 Hours Target)</option>
                      <option value="Medium">Medium (Standard SLA)</option>
                      <option value="Low">Low</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-zinc-300 mb-1">Completion Window (Days)</label>
                    <input
                      type="number"
                      min={1}
                      max={60}
                      value={expectedDays}
                      onChange={(e) => setExpectedDays(Number(e.target.value))}
                      className="w-full p-2.5 rounded-xl bg-[#10131C] border border-white/[0.08] text-xs text-[#F5F5F5]"
                    />
                  </div>
                </div>

                {/* 4. Assignment Date & Expected Completion Date */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-semibold text-zinc-300 mb-1 flex items-center gap-1.5">
                      <Calendar className="w-3.5 h-3.5 text-[#F36B21]" />
                      <span>Assignment Date</span>
                    </label>
                    <input
                      type="date"
                      value={assignmentDate}
                      onChange={(e) => setAssignmentDate(e.target.value)}
                      className="w-full p-2.5 rounded-xl bg-[#10131C] border border-white/[0.08] text-xs text-[#F5F5F5]"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-zinc-300 mb-1 flex items-center gap-1.5">
                      <Clock className="w-3.5 h-3.5 text-[#138A4B]" />
                      <span>Expected Completion Date</span>
                    </label>
                    <input
                      type="date"
                      value={expectedCompletionDate}
                      onChange={(e) => setExpectedCompletionDate(e.target.value)}
                      className="w-full p-2.5 rounded-xl bg-[#10131C] border border-white/[0.08] text-xs text-[#F5F5F5]"
                    />
                  </div>
                </div>

                {/* 5. Assignment Instructions */}
                <div>
                  <label className="block text-xs font-semibold text-zinc-300 mb-1">
                    Assignment Instructions
                  </label>
                  <textarea
                    rows={2}
                    value={assignmentInstructions}
                    onChange={(e) => setAssignmentInstructions(e.target.value)}
                    placeholder="e.g. Conduct physical road inspection, perform core sampling, and upload before/after photos upon repair completion."
                    className="w-full p-3 rounded-xl bg-[#10131C] border border-white/[0.08] text-xs text-[#F5F5F5] placeholder-[#A1A1AA]/40"
                  />
                </div>

                {/* 6. Dispatch Confirmation Summary */}
                <div className="p-3.5 rounded-2xl bg-[#10131C] border border-white/[0.08] space-y-2">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-[#A1A1AA] flex items-center gap-1.5">
                    <ShieldCheck className="w-3.5 h-3.5 text-[#F36B21]" />
                    <span>Dispatch Confirmation Summary</span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-[11px] text-[#A1A1AA]">
                    <div>Division: <span className="text-[#F5F5F5] font-semibold">{currentDept?.code} ({currentDept?.name})</span></div>
                    <div>Officer: <span className="text-[#F5F5F5] font-semibold">{selectedOfficer ? selectedOfficer.full_name : `${currentDept?.head_name} (Head)`}</span></div>
                    <div>Priority: <span className="text-[#F5F5F5] font-semibold">{assignedPriority}</span></div>
                    <div>Target Date: <span className="text-[#F5F5F5] font-semibold">{expectedCompletionDate || 'Standard SLA'}</span></div>
                  </div>
                  <label className="flex items-center gap-2 pt-2 border-t border-white/[0.06] cursor-pointer">
                    <input
                      type="checkbox"
                      checked={dispatchConfirmed}
                      onChange={(e) => {
                        setDispatchConfirmed(e.target.checked)
                        setValidationError(null)
                      }}
                      className="rounded border-zinc-700 bg-zinc-800 text-[#F36B21] focus:ring-0 cursor-pointer"
                    />
                    <span className="text-xs font-semibold text-[#F5F5F5]">I confirm this authoritative work order dispatch</span>
                  </label>
                </div>

                {/* Action Buttons */}
                <div className="flex items-center justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => {
                      setDispatchModalOpen(false)
                      setValidationError(null)
                      setDispatchConfirmed(false)
                    }}
                    className="px-4 py-2 rounded-xl text-[#A1A1AA] text-xs font-semibold hover:bg-white/[0.05] cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={actionLoading || !dispatchConfirmed}
                    className={`px-5 py-2 rounded-xl font-semibold text-xs shadow-xs flex items-center gap-1.5 transition-all cursor-pointer ${
                      dispatchConfirmed && !actionLoading
                        ? 'bg-[#F36B21] hover:bg-[#E05A10] text-white shadow-md shadow-[#F36B21]/20'
                        : 'bg-white/[0.05] text-[#A1A1AA] cursor-not-allowed'
                    }`}
                  >
                    <Send className="w-3.5 h-3.5" />
                    <span>{actionLoading ? 'Dispatching...' : 'Dispatch Work Order'}</span>
                  </button>
                </div>
              </form>
            </div>
          </div>
        )
      })()}

      {/* MODAL 3: Return Work for Correction */}
      {returnModalOpen && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#141722]/85 rounded-3xl p-6 sm:p-7 max-w-md w-full border border-white/[0.08] shadow-2xl space-y-4">
            <div>
              <h3 className="text-base font-bold text-[#F5F5F5]">Return Work for Correction</h3>
              <p className="text-xs text-[#A1A1AA] mt-1">
                Provide an explanatory note on what needs correction before final closure of {selectedComplaint?.complaint_id}.
              </p>
            </div>

            <form onSubmit={handleReturnCorrection} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-zinc-300 mb-1">
                  Correction Requirement (Mandatory)
                </label>
                <textarea
                  required
                  rows={3}
                  value={returnNotes}
                  onChange={(e) => setReturnNotes(e.target.value)}
                  placeholder="e.g. Surface asphalt layer is uneven; please re-compact and upload clear post-repair photograph."
                  className="w-full p-3 rounded-xl bg-[#10131C] border border-white/[0.08] text-xs text-[#F5F5F5] focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setReturnModalOpen(false)}
                  className="px-4 py-2 rounded-xl text-[#A1A1AA] text-xs font-semibold hover:bg-white/[0.05] cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold shadow-xs cursor-pointer"
                >
                  Return to Department
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
