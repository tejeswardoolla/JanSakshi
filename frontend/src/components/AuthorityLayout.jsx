import React, { useState } from 'react'
import { Link, useLocation, useNavigate, Navigate } from 'react-router-dom'
import {
  LayoutDashboard, FileText, CheckCircle2, Building2, Flame,
  History, Shield, LogOut, Menu, X, ArrowLeft, ExternalLink,
  Mail, Layers, UserCheck, ChevronRight, Activity, Bell,
  Sparkles, MapPin, Wrench, Cpu, CheckSquare, Search
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'

export default function AuthorityLayout({ children, pageTitle, breadcrumbs = [] }) {
  const { user, isAuthenticated, logout, loading } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const [sidebarOpen, setSidebarOpen] = useState(false)

  // Enforce access control
  if (!loading && !isAuthenticated) {
    return <Navigate to="/authority/login" replace state={{ from: location }} />
  }

  const handleLogout = () => {
    logout()
    navigate('/authority/login')
  }

  // Strict role-specific navigation definitions
  const getNavSections = () => {
    const role = user?.role || 'authority_officer'

    if (role === 'admin') {
      return [
        {
          group: 'INTAKE & MANAGEMENT',
          items: [
            { label: 'Management Centre', path: '/authority', icon: LayoutDashboard, exact: true },
            { label: 'Incoming Complaints', path: '/authority/complaints', icon: FileText },
            { label: 'Gmail Intake Desk', path: '/authority/email-management', icon: Mail },
          ]
        },
        {
          group: 'AI & PHYSICAL ISSUES',
          items: [
            { label: 'Duplicate Review Desk', path: '/authority/duplicates', icon: Layers },
            { label: 'Critical Escalations', path: '/authority/escalations', icon: Flame },
          ]
        },
        {
          group: 'GOVERNANCE & AUDIT',
          items: [
            { label: 'Department Directory', path: '/authority/departments', icon: Building2 },
            { label: 'System Audit Trail', path: '/authority/audit', icon: History },
          ]
        }
      ]
    } else if (role === 'department_officer') {
      const activeDeptId = localStorage.getItem('jansakshi_active_dept_id') || (user?.department_id || 1).toString()
      const activeDeptCode = localStorage.getItem('jansakshi_active_dept_code') || user?.department_code || 'RPW'
      return [
        {
          group: `${activeDeptCode} OPERATIONS`,
          items: [
            { label: `${activeDeptCode} Dashboard`, path: `/authority?dept=${activeDeptId}`, icon: LayoutDashboard, exact: true },
            { label: 'My Assigned Work', path: '/authority/complaints', icon: FileText },
            { label: 'Field Inspection Queue', path: '/authority/inspection-queue', icon: Wrench },
          ]
        },
        {
          group: 'DIVISION TOOLS',
          items: [
            { label: 'Switch Division Desk', path: '/authority/select-department', icon: Layers },
            { label: 'Division SLA Metrics', path: '/authority/departments', icon: Building2 },
            { label: 'Division Activity Trail', path: '/authority/audit', icon: History },
          ]
        }
      ]
    } else {
      // authority_officer — strictly Civic Decisions, Department Assignment & Monitoring
      return [
        {
          group: 'CIVIC DECISIONS',
          items: [
            { label: 'Decision & Dispatch', path: '/authority', icon: LayoutDashboard, exact: true },
            { label: 'Assignment Queue', path: '/authority/verification-queue', icon: CheckCircle2 },
            { label: 'Resolution Review', path: '/authority/resolution-review', icon: CheckSquare },
            { label: 'All Prepared Grievances', path: '/authority/complaints', icon: FileText },
            { label: 'Critical Escalations', path: '/authority/escalations', icon: Flame },
          ]
        },
        {
          group: 'MUNICIPAL DISPATCH',
          items: [
            { label: 'Department Workload', path: '/authority/departments', icon: Building2 },
            { label: 'Decision Audit History', path: '/authority/audit', icon: History },
          ]
        }
      ]
    }
  }

  const navSections = getNavSections()

  const getRoleBadge = (role) => {
    switch (role) {
      case 'admin':
        return { label: 'Admin (AI & Intake)', color: '#EF4444', bg: 'bg-red-500/10 text-red-400 border-red-500/30' }
      case 'department_officer':
        const activeDeptCode = localStorage.getItem('jansakshi_active_dept_code') || user?.department_code || 'RPW'
        return { label: `${activeDeptCode} Field Officer`, color: '#38BDF8', bg: 'bg-sky-500/10 text-sky-400 border-sky-500/30' }
      default:
        return { label: 'Authority Officer', color: '#F36B21', bg: 'bg-[#F36B21]/10 text-[#F36B21] border-[#F36B21]/30' }
    }
  }

  const roleInfo = getRoleBadge(user?.role)

  const isLinkActive = (item) => {
    const basePath = item.path.split('?')[0]
    if (item.exact) {
      return location.pathname === basePath
    }
    return location.pathname === basePath || (basePath !== '/authority' && location.pathname.startsWith(`${basePath}/`))
  }

  return (
    <div className="min-h-screen bg-[#090B10] text-[#F5F5F5] flex flex-col md:flex-row antialiased selection:bg-[#F36B21] selection:text-white relative overflow-x-hidden font-sans">
      {/* Saffron & dark ambient lighting */}
      <div className="fixed top-0 left-1/4 w-[700px] h-[450px] bg-gradient-to-b from-[#F36B21]/10 via-[#102B4E]/15 to-transparent rounded-full blur-[140px] pointer-events-none z-0" />
      <div className="fixed bottom-10 right-10 w-[500px] h-[450px] bg-[#102B4E]/20 rounded-full blur-[160px] pointer-events-none z-0" />

      {/* Mobile Top Bar */}
      <div className="md:hidden flex items-center justify-between px-5 py-3.5 bg-[#10131C]/90 backdrop-blur-xl border-b border-white/[0.08] sticky top-0 z-50">
        <Link to="/authority" className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-full overflow-hidden border border-[#F36B21]/40 flex items-center justify-center shadow-xs">
            <img
              src="/assets/jansakshi-logo.jpg"
              alt="JanSakshi Logo"
              className="w-full h-full object-cover"
            />
          </div>
          <span className="font-extrabold text-sm tracking-tight text-[#F5F5F5]">JanSakshi Staff</span>
        </Link>
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="p-2 rounded-xl bg-white/[0.05] hover:bg-white/[0.1] text-zinc-300 cursor-pointer"
        >
          {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {/* Desktop Sidebar (Dark Glassmorphism) */}
      <aside
        className={`fixed md:sticky top-0 h-screen w-64 bg-[#10131C]/85 backdrop-blur-xl border-r border-white/[0.08] p-5 flex flex-col justify-between z-40 transition-transform duration-300 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
        }`}
      >
        <div className="flex-1 overflow-y-auto pr-1">
          {/* Logo & Portal Identity */}
          <Link to="/authority" className="flex items-center gap-3 mb-6 pb-5 border-b border-white/[0.08] group">
            <div className="w-10 h-10 rounded-full overflow-hidden border-2 border-[#F36B21]/40 group-hover:border-[#F36B21] transition-all duration-300 flex-shrink-0 shadow-md">
              <img
                src="/assets/jansakshi-logo.jpg"
                alt="JanSakshi Logo"
                className="w-full h-full object-cover"
              />
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <span className="font-extrabold text-base tracking-tight text-[#F5F5F5]">JanSakshi</span>
                <span className="text-[9px] uppercase font-bold tracking-wider px-1.5 py-0.2 rounded-full bg-[#F36B21]/15 text-[#F36B21] border border-[#F36B21]/30">
                  Staff
                </span>
              </div>
              <p className="text-[11px] text-[#A1A1AA] font-medium">Municipal Operations</p>
            </div>
          </Link>

          {/* User Profile Card */}
          <div className="p-3.5 rounded-2xl bg-[#141722]/85 backdrop-blur-md border border-white/[0.08] mb-6">
            <div className="flex items-center gap-2.5">
              <div className="w-9 h-9 rounded-xl bg-[#191D2A] border border-white/[0.08] flex items-center justify-center text-xs font-bold text-[#F5F5F5] shadow-xs">
                {user?.full_name ? user.full_name.charAt(0).toUpperCase() : 'U'}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-xs font-bold text-[#F5F5F5] truncate">{user?.full_name || 'Staff Officer'}</div>
                <div className="text-[10px] text-[#A1A1AA] font-mono truncate">{user?.username || 'officer'}</div>
              </div>
            </div>
            <div className="mt-2.5 pt-2 border-t border-white/[0.06] flex items-center justify-between">
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${roleInfo.bg}`}>
                {roleInfo.label}
              </span>
              {user?.role === 'department_officer' && (
                <Link
                  to="/authority/select-department"
                  className="text-[10px] font-semibold text-[#F36B21] hover:underline"
                >
                  Switch Desk ▾
                </Link>
              )}
            </div>
          </div>

          {/* Navigation Groups */}
          <nav className="space-y-6">
            {navSections.map((sec, idx) => (
              <div key={idx}>
                <div className="text-[10px] font-bold text-[#A1A1AA]/70 uppercase tracking-wider mb-2 px-2">
                  {sec.group}
                </div>
                <div className="space-y-1">
                  {sec.items.map((item, itemIdx) => {
                    const active = isLinkActive(item)
                    const Icon = item.icon
                    return (
                      <Link
                        key={itemIdx}
                        to={item.path}
                        onClick={() => setSidebarOpen(false)}
                        className={`flex items-center justify-between px-3 py-2 rounded-xl text-xs font-semibold transition-all ${
                          active
                            ? 'bg-[#191D2A] text-white border border-[#F36B21]/30 shadow-xs'
                            : 'text-[#A1A1AA] hover:text-[#F5F5F5] hover:bg-white/[0.04]'
                        }`}
                      >
                        <div className="flex items-center gap-2.5">
                          <Icon className={`w-4 h-4 ${active ? 'text-[#F36B21]' : 'text-[#A1A1AA]'}`} />
                          <span>{item.label}</span>
                        </div>
                        {active && <div className="w-1.5 h-1.5 rounded-full bg-[#F36B21] shadow-[0_0_8px_#F36B21]" />}
                      </Link>
                    )
                  })}
                </div>
              </div>
            ))}
          </nav>
        </div>

        {/* Sidebar Footer */}
        <div className="pt-4 border-t border-white/[0.08] space-y-2">
          <Link
            to="/"
            target="_blank"
            className="flex items-center justify-between px-3 py-2 rounded-xl text-xs font-semibold text-[#A1A1AA] hover:text-[#F5F5F5] hover:bg-white/[0.04] transition-all"
          >
            <div className="flex items-center gap-2">
              <ExternalLink className="w-3.5 h-3.5 text-[#A1A1AA]" />
              <span>Public Citizen Portal</span>
            </div>
            <span className="text-[9px] text-[#A1A1AA] font-mono">↗</span>
          </Link>
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-semibold text-red-400 hover:bg-red-500/10 hover:text-red-300 transition-all cursor-pointer"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span>Sign Out Desk</span>
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 relative z-10">
        {/* Top Minimal Staff Header (Dark Glassmorphism) */}
        <header className="h-16 bg-[#10131C]/80 backdrop-blur-xl border-b border-white/[0.08] px-6 sm:px-8 flex items-center justify-between sticky top-0 z-30">
          {/* Breadcrumbs or Page Title */}
          <div className="flex items-center gap-2 text-xs">
            {breadcrumbs.length > 0 ? (
              breadcrumbs.map((b, i) => {
                const label = typeof b === 'string' ? b : (b?.label || '')
                const path = typeof b === 'object' ? b?.path : null
                const isLast = i === breadcrumbs.length - 1
                return (
                  <React.Fragment key={i}>
                    {path ? (
                      <Link to={path} className="text-[#A1A1AA] hover:text-[#F5F5F5] font-medium transition-colors">
                        {label}
                      </Link>
                    ) : (
                      <span className={isLast ? "text-[#F5F5F5] font-semibold" : "text-[#A1A1AA] font-medium"}>
                        {label}
                      </span>
                    )}
                    {!isLast && <span className="text-zinc-600">/</span>}
                  </React.Fragment>
                )
              })
            ) : pageTitle ? (
              <>
                <span className="font-semibold text-[#A1A1AA]">Operations Desk</span>
                <span className="text-zinc-600">/</span>
                <span className="font-bold text-[#F5F5F5]">{pageTitle}</span>
              </>
            ) : (
              <span className="font-semibold text-[#F5F5F5]">Operations Desk</span>
            )}
          </div>

          {/* Quick Actions / Role Indicator */}
          <div className="flex items-center gap-3">
            {user?.role === 'department_officer' && (
              <Link
                to="/authority/select-department"
                className="px-3 py-1 rounded-full bg-[#141722] border border-white/[0.08] text-[#F5F5F5] hover:border-[#F36B21]/40 text-xs font-semibold shadow-xs flex items-center gap-1.5 transition-all"
              >
                <Layers className="w-3.5 h-3.5 text-[#F36B21]" />
                <span>Division: {localStorage.getItem('jansakshi_active_dept_code') || user?.department_code || 'RPW'}</span>
                <span className="text-[10px] text-[#A1A1AA]">▾</span>
              </Link>
            )}
            <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-[#141722] border border-white/[0.08] text-xs font-semibold text-[#F5F5F5] shadow-xs">
              <span className="w-2 h-2 rounded-full bg-[#138A4B] animate-pulse shadow-[0_0_8px_#138A4B]" />
              <span>Live Desk</span>
            </div>
          </div>
        </header>

        {/* Page Main Content */}
        <main className="flex-1 p-6 sm:p-8 md:p-10">{children}</main>
      </div>
    </div>
  )
}
