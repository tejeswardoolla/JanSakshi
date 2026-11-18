import React, { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import {
  Shield, Wrench, Droplets, CloudRain, Trash2, Zap, Trees,
  ArrowRight, Lock, CheckCircle2, RefreshCw, AlertCircle,
  Building2, LogOut, ChevronRight, User, Layers, ArrowLeft
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'

// Department Card Metadatas & Visual Assets
const DEPARTMENT_CONFIGS = {
  RPW: {
    name: 'Roads & Public Works',
    code: 'RPW',
    dbId: 1,
    icon: Wrench,
    accentColor: '#F36B21',
    heroImage: '/assets/dept_rpw.jpg',
    tag: 'Field Infrastructure',
    highlight: 'Potholes, asphalt road damages, damaged footpaths, flyovers & safety barriers'
  },
  WSS: {
    name: 'Water Supply & Sewerage',
    code: 'WSD',
    altCode: 'WSS',
    dbId: 3,
    icon: Droplets,
    accentColor: '#0284C7',
    heroImage: '/assets/dept_wss.jpg',
    tag: 'Potable Utilities',
    highlight: 'Pipeline leakages, water contamination, low pressure, sewer backflow & potable supply'
  },
  DRN: {
    name: 'Storm Water Drainage',
    code: 'DRN',
    dbId: 4,
    icon: CloudRain,
    accentColor: '#0D9488',
    heroImage: '/assets/dept_drn.jpg',
    tag: 'Flood Prevention',
    highlight: 'Clogged drains, open drainage canals, monsoon storm water overflow & waterlogging'
  },
  SWM: {
    name: 'Sanitation & Waste Management',
    code: 'SWM',
    dbId: 2,
    icon: Trash2,
    accentColor: '#16A34A',
    heroImage: '/assets/dept_swm.jpg',
    tag: 'Civic Hygiene',
    highlight: 'Community garbage dumps, community bin overflow, waste clearing & street sweeping'
  },
  ESM: {
    name: 'Electrical & Street Lighting',
    code: 'ESM',
    dbId: 5,
    icon: Zap,
    accentColor: '#D97706',
    heroImage: '/assets/dept_esm.jpg',
    tag: 'Grid & Illuminations',
    highlight: 'Broken streetlights, dangling overhead cables, unlit thoroughfares & transformer safety'
  },
  PID: {
    name: 'Public Infrastructure & Parks',
    code: 'PID',
    dbId: 6,
    icon: Trees,
    accentColor: '#7C3AED',
    heroImage: '/assets/dept_pid.jpg',
    tag: 'Civic Spaces',
    highlight: 'Park maintenance, civic gardens, public benches, open recreational amenities & boundary walls'
  }
}

export default function DepartmentSelectionPage() {
  const { user, isAuthenticated, logout, authFetch, loading: authLoading } = useAuth()
  const navigate = useNavigate()
  const [departments, setDepartments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      navigate('/authority/login')
      return
    }
    fetchDepartments()
  }, [authLoading, isAuthenticated])

  const fetchDepartments = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await authFetch('/api/authority/departments/selection')
      if (!res.ok) throw new Error('Failed to load department selection data.')
      const json = await res.json()
      setDepartments(json.departments || [])

      // If user is only authorized for a single department, direct them straight in
      const authorizedDepts = (json.departments || []).filter((d) => d.is_authorized)
      if (authorizedDepts.length === 1 && !json.user?.has_all_departments) {
        selectDepartment(authorizedDepts[0])
      }
    } catch (err) {
      setError(err.message || 'Error fetching department directory.')
    } finally {
      setLoading(false)
    }
  }

  const selectDepartment = (dept) => {
    if (!dept.is_authorized) return
    localStorage.setItem('jansakshi_active_dept_id', dept.id.toString())
    localStorage.setItem('jansakshi_active_dept_code', dept.code)
    navigate(`/authority?dept=${dept.id}`)
  }

  const handleLogout = () => {
    logout()
    navigate('/authority/login')
  }

  return (
    <div className="min-h-screen bg-[#090B10] text-[#F5F5F5] flex flex-col justify-between p-4 sm:p-8 relative overflow-hidden antialiased font-sans">
      {/* Saffron and navy ambient glows */}
      <div className="absolute top-0 right-1/4 w-[700px] h-[500px] bg-gradient-to-b from-[#F36B21]/15 via-[#102B4E]/20 to-transparent rounded-full blur-[140px] pointer-events-none" />
      <div className="absolute bottom-0 left-10 w-[500px] h-[400px] bg-[#102B4E]/30 rounded-full blur-[160px] pointer-events-none" />

      {/* Top Header */}
      <header className="w-full max-w-7xl mx-auto flex items-center justify-between py-4 border-b border-white/[0.08] relative z-10">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full overflow-hidden border-2 border-[#F36B21]/40 flex items-center justify-center shadow-sm">
            <img
              src="/assets/jansakshi-logo.jpg"
              alt="JanSakshi Logo"
              className="w-full h-full object-cover"
            />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-extrabold text-base tracking-tight text-[#F5F5F5]">JanSakshi</span>
              <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-[#F36B21]/15 text-[#F36B21] border border-[#F36B21]/30">
                Staff Desk
              </span>
            </div>
            <p className="text-[11px] text-[#A1A1AA] font-medium">Department Field Operations</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-xl bg-[#141722]/85 border border-white/[0.08] text-xs">
            <User className="w-3.5 h-3.5 text-[#A1A1AA]" />
            <span className="font-semibold text-[#F5F5F5]">{user?.full_name || 'Department Officer'}</span>
            <span className="text-[10px] font-mono text-[#F36B21] bg-[#F36B21]/20 px-1.5 py-0.5 rounded">
              {user?.username}
            </span>
          </div>
          <button
            onClick={handleLogout}
            className="px-3 py-1.5 rounded-xl bg-[#141722]/85 hover:bg-[#191D2A] border border-white/[0.08] text-[#A1A1AA] hover:text-[#F5F5F5] text-xs font-semibold flex items-center gap-1.5 shadow-sm transition-all cursor-pointer"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span>Sign Out</span>
          </button>
        </div>
      </header>

      {/* Hero Header */}
      <main className="w-full max-w-7xl mx-auto flex-1 my-8 relative z-10">
        <div className="text-center max-w-2xl mx-auto mb-10">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#141722]/85 border border-white/[0.08] text-[11px] font-semibold text-[#A1A1AA] mb-3 shadow-xs">
            <Layers className="w-3.5 h-3.5 text-[#F36B21]" />
            <span>AUTHORISED MUNICIPAL DESKS</span>
          </div>
          <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-[#F5F5F5]">
            Department Operations
          </h1>
          <p className="text-sm text-[#A1A1AA] mt-2 leading-relaxed">
            Select your authorised department to manage assigned work orders, conduct physical field inspections, and record repair resolution progress.
          </p>
        </div>

        {error && (
          <div className="max-w-md mx-auto mb-6 p-4 rounded-2xl bg-red-500/10 border border-red-500/30 text-red-400 text-xs flex items-center gap-3">
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* 6 Department Cards Grid */}
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <div key={i} className="h-80 rounded-3xl bg-[#141722]/50 border border-white/[0.08] animate-pulse" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {departments.map((dept) => {
              const code = dept.code === 'WSD' ? 'WSS' : dept.code
              const meta = DEPARTMENT_CONFIGS[code] || DEPARTMENT_CONFIGS[dept.code] || DEPARTMENT_CONFIGS.RPW
              const Icon = meta.icon
              const isLocked = !dept.is_authorized

              return (
                <div
                  key={dept.id}
                  onClick={() => !isLocked && selectDepartment(dept)}
                  className={`group relative rounded-3xl overflow-hidden border transition-all duration-300 flex flex-col justify-between ${
                    isLocked
                      ? 'bg-[#10131C]/60 border-white/[0.04] opacity-50 cursor-not-allowed'
                      : 'bg-[#141722]/85 border-white/[0.08] hover:border-[#F36B21]/40 shadow-xl hover:shadow-[#F36B21]/10 hover:-translate-y-1 cursor-pointer'
                  }`}
                >
                  {/* Card Visual Hero Thumbnail */}
                  <div className="relative h-44 w-full overflow-hidden bg-[#10131C]">
                    <img
                      src={meta.heroImage}
                      alt={dept.name}
                      className={`w-full h-full object-cover transition-transform duration-700 ${
                        isLocked ? 'grayscale' : 'group-hover:scale-105'
                      }`}
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-[#141722] via-[#141722]/40 to-transparent" />

                    {/* Division Pill Badge */}
                    <div className="absolute top-3 left-3 flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#10131C]/90 backdrop-blur-md border border-white/[0.1] shadow-xs">
                      <Icon className="w-3.5 h-3.5" style={{ color: meta.accentColor }} />
                      <span className="text-[11px] font-bold text-[#F5F5F5]">{meta.code}</span>
                      <span className="text-[10px] text-[#A1A1AA]">• {meta.tag}</span>
                    </div>

                    {/* Complaint Count Badge */}
                    <div className="absolute bottom-3 left-3 text-white">
                      <div className="text-xl font-bold tracking-tight leading-none text-[#F5F5F5]">
                        {dept.complaint_count}{' '}
                        <span className="text-xs font-normal text-[#A1A1AA]">Active Work Orders</span>
                      </div>
                    </div>

                    {/* Status Badge Top Right */}
                    <div className="absolute top-3 right-3">
                      {isLocked ? (
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-black/70 backdrop-blur-md text-zinc-400 text-[10px] font-bold border border-white/[0.06]">
                          <Lock className="w-3 h-3 text-amber-400" />
                          <span>Restricted</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-[#138A4B]/80 backdrop-blur-md text-white text-[10px] font-bold border border-[#138A4B]/40 shadow-[0_0_8px_#138A4B]/40">
                          <CheckCircle2 className="w-3 h-3" />
                          <span>Authorised</span>
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Card Body */}
                  <div className="p-5 flex-1 flex flex-col justify-between">
                    <div>
                      <h3 className="text-base font-bold text-[#F5F5F5] group-hover:text-[#F36B21] transition-colors">
                        {dept.name}
                      </h3>
                      <p className="text-xs text-[#A1A1AA] mt-1 leading-relaxed">
                        {meta.highlight}
                      </p>
                    </div>

                    <div className="mt-5 pt-4 border-t border-white/[0.06] flex items-center justify-between">
                      <span className="text-[11px] font-semibold text-[#A1A1AA]">
                        SLA Target: <strong className="text-[#F5F5F5]">{dept.sla_days} Days</strong>
                      </span>

                      {isLocked ? (
                        <span className="text-xs text-zinc-500 font-semibold flex items-center gap-1">
                          <Lock className="w-3.5 h-3.5" />
                          <span>Role Locked</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 text-xs font-bold text-[#F36B21] group-hover:text-[#F36B21] transition-colors">
                          <span>Enter Workspace</span>
                          <ArrowRight className="w-3.5 h-3.5 transition-transform group-hover:translate-x-1" />
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="w-full max-w-7xl mx-auto pt-6 border-t border-white/[0.08] text-center text-xs text-[#A1A1AA] relative z-10 flex flex-col sm:flex-row items-center justify-between gap-3">
        <span>JanSakshi Municipal Operations • AI-Powered Grievance Platform</span>
        <div className="flex items-center gap-4">
          <Link to="/" className="text-[#A1A1AA] hover:text-[#F5F5F5] transition-colors">Citizen Portal</Link>
          <span>•</span>
          <Link to="/authority/login" className="text-[#A1A1AA] hover:text-[#F5F5F5] transition-colors">Switch User</Link>
        </div>
      </footer>
    </div>
  )
}
