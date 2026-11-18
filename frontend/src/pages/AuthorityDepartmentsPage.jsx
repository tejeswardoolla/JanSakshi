import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  Building2, Users, Clock, Mail, CheckCircle2, AlertTriangle,
  RefreshCw, ArrowRight, Shield, Layers, Wrench, CheckCircle,
  FileCheck2, Activity, Percent
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import AuthorityLayout from '../components/AuthorityLayout'

export default function AuthorityDepartmentsPage() {
  const { authFetch, user } = useAuth()
  const [departments, setDepartments] = useState([])
  const [overviewMetrics, setOverviewMetrics] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const isDeptOfficer = user?.role === 'department_officer'
  const activeDeptId = localStorage.getItem('jansakshi_active_dept_id') || (user?.department_id || 1).toString()
  const activeDeptCode = localStorage.getItem('jansakshi_active_dept_code') || user?.department_code || 'RPW'
  const activeDeptName = localStorage.getItem('jansakshi_active_dept_name') || 'Roads & Public Works'

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    setLoading(true)
    setError(null)
    try {
      const deptUrl = isDeptOfficer
        ? `/api/authority/departments?department_id=${activeDeptId}`
        : '/api/authority/departments'
      const overUrl = isDeptOfficer
        ? `/api/authority/overview?department_id=${activeDeptId}`
        : '/api/authority/overview'

      const [deptRes, overRes] = await Promise.all([
        authFetch(deptUrl),
        authFetch(overUrl)
      ])

      if (deptRes.ok) {
        const dJson = await deptRes.json()
        setDepartments(dJson.departments || [])
      }

      if (overRes.ok) {
        const oJson = await overRes.json()
        setOverviewMetrics(oJson.department_metrics || [])
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const combinedDepts = departments.map((d) => {
    const metric = overviewMetrics.find((m) => m.code === d.code) || {}
    const totalAssigned = d.total_assigned ?? metric.total_assigned ?? 0
    const resolved = d.resolved_complaints ?? metric.resolved ?? 0
    const overdue = d.overdue_work_orders ?? 0
    const slaRate = d.sla_compliance_rate ?? d.performance_rate ?? (totalAssigned > 0 ? Math.round(((totalAssigned - overdue) / totalAssigned) * 1000) / 10 : 100.0)
    const resRate = d.resolution_rate ?? (totalAssigned > 0 ? Math.round((resolved / totalAssigned) * 1000) / 10 : 0.0)

    return {
      ...d,
      total_assigned: totalAssigned,
      pending_inspections: d.pending_inspections ?? metric.pending ?? 0,
      in_progress_repairs: d.in_progress_repairs ?? metric.in_progress ?? 0,
      resolved_complaints: resolved,
      overdue_work_orders: overdue,
      sla_compliance_rate: slaRate,
      resolution_rate: resRate
    }
  })

  return (
    <AuthorityLayout
      pageTitle={isDeptOfficer ? `${activeDeptName} Performance & SLA` : "Municipal Departments Directory"}
      breadcrumbs={isDeptOfficer ? [activeDeptName, 'Performance SLA'] : ['Operations Desk', 'Departments']}
    >
      <div className="space-y-6 max-w-7xl mx-auto font-sans">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-white/[0.08]">
          <div>
            <h1 className="text-xl font-bold tracking-tight text-[#F5F5F5]">
              {isDeptOfficer ? `${activeDeptName} (${activeDeptCode}) Performance` : "Municipal Divisions Workload & SLA"}
            </h1>
            <p className="text-xs text-[#A1A1AA] mt-0.5">
              {isDeptOfficer
                ? `Authorized division workload, statutory SLA targets, and active work orders for ${activeDeptName}.`
                : "Six statutory municipal engineering divisions, division leadership, and real-time SLA metrics."}
            </p>
          </div>
          <button
            onClick={fetchData}
            className="px-3.5 py-2 rounded-xl bg-[#141722]/85 hover:bg-white/[0.03] border border-white/[0.08] text-xs font-semibold text-zinc-300 flex items-center gap-1.5 shadow-xs cursor-pointer transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Sync Metrics</span>
          </button>
        </div>

        {error && (
          <div className="p-4 rounded-2xl bg-red-500/10 border border-red-500/30 text-red-400 text-xs">
            {error}
          </div>
        )}

        {/* Departments View */}
        {loading ? (
          <div className="py-24 text-center">
            <RefreshCw className="w-8 h-8 text-[#F36B21] animate-spin mx-auto mb-3" />
            <p className="text-xs text-[#A1A1AA] font-medium">Computing division workloads...</p>
          </div>
        ) : (
          <div className="space-y-6">
            {combinedDepts.map((dept) => (
              <div key={dept.id} className="bg-[#141722]/85 rounded-3xl border border-white/[0.08] p-6 sm:p-7 shadow-xs space-y-6">
                <div className="flex items-center justify-between flex-wrap gap-4 pb-4 border-b border-white/[0.08]">
                  <div className="flex items-center gap-3.5">
                    <div className="w-12 h-12 rounded-2xl bg-[#10131C] border border-white/[0.08] flex items-center justify-center font-bold text-base text-[#F36B21]">
                      {dept.code}
                    </div>
                    <div>
                      <h2 className="text-lg font-bold text-[#F5F5F5]">{dept.name}</h2>
                      <p className="text-xs text-[#A1A1AA] mt-0.5">{dept.description}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold px-3 py-1 rounded-full bg-[#10131C] border border-white/[0.08] text-zinc-300">
                      SLA: {dept.sla_days} Days
                    </span>
                  </div>
                </div>

                {/* Metrics Grid */}
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
                  <div className="p-4 rounded-2xl bg-[#10131C] border border-white/[0.08]">
                    <span className="text-[10px] font-bold text-[#A1A1AA] uppercase block">Total Assigned</span>
                    <span className="text-2xl font-extrabold text-[#F5F5F5] mt-1 block">{dept.total_assigned}</span>
                  </div>

                  <div className="p-4 rounded-2xl bg-[#10131C] border border-white/[0.08]">
                    <span className="text-[10px] font-bold text-amber-400 uppercase block">Pending Inspection</span>
                    <span className="text-2xl font-extrabold text-[#F5F5F5] mt-1 block">{dept.pending_inspections}</span>
                  </div>

                  <div className="p-4 rounded-2xl bg-[#10131C] border border-white/[0.08]">
                    <span className="text-[10px] font-bold text-sky-400 uppercase block">In-Progress Repairs</span>
                    <span className="text-2xl font-extrabold text-[#F5F5F5] mt-1 block">{dept.in_progress_repairs}</span>
                  </div>

                  <div className="p-4 rounded-2xl bg-[#10131C] border border-white/[0.08]">
                    <span className="text-[10px] font-bold text-emerald-400 uppercase block">Resolved Complaints</span>
                    <span className="text-2xl font-extrabold text-[#F5F5F5] mt-1 block">{dept.resolved_complaints}</span>
                  </div>

                  <div className="p-4 rounded-2xl bg-[#10131C] border border-white/[0.08]">
                    <span className="text-[10px] font-bold text-[#A1A1AA] uppercase block">SLA Compliance</span>
                    <span className="text-2xl font-extrabold text-emerald-400 mt-1 block">{dept.sla_compliance_rate}%</span>
                  </div>

                  <div className="p-4 rounded-2xl bg-[#10131C] border border-white/[0.08]">
                    <span className="text-[10px] font-bold text-[#A1A1AA] uppercase block">Resolution Rate</span>
                    <span className="text-2xl font-extrabold text-indigo-700 mt-1 block">{dept.resolution_rate}%</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </AuthorityLayout>
  )
}
