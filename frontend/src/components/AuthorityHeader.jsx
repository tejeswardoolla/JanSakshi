import React from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { Shield, LayoutDashboard, FileText, CheckCircle2, Mail, LogOut, UserCheck } from 'lucide-react'
import { useAuth } from '../context/AuthContext'

export default function AuthorityHeader() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const handleLogout = () => {
    logout()
    navigate('/authority/login')
  }

  const navItems = [
    { label: 'Overview', path: '/authority', icon: LayoutDashboard },
    { label: 'All Complaints', path: '/authority/complaints', icon: FileText },
    { label: 'Review Desk', path: '/duplicates', icon: CheckCircle2 },
    { label: 'Email Desk', path: '/email-management', icon: Mail },
  ]

  const getRoleBadge = (role) => {
    switch (role) {
      case 'admin':
        return { label: 'Admin', color: 'bg-red-500/20 text-red-400 border-red-500/30' }
      case 'department_officer':
        return { label: 'Dept Officer', color: 'bg-blue-500/20 text-blue-400 border-blue-500/30' }
      default:
        return { label: 'Verification Officer', color: 'bg-[#F36B21]/20 text-[#F36B21] border-[#F36B21]/30' }
    }
  }

  const roleInfo = getRoleBadge(user?.role)

  return (
    <header className="sticky top-0 z-40 bg-[#08090B]/95 backdrop-blur-md border-b border-white/10 px-6 py-3.5 transition-all">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        {/* Brand identity */}
        <div className="flex items-center gap-6">
          <Link to="/authority" className="flex items-center gap-3 group">
            <div className="w-9 h-9 rounded-full overflow-hidden border border-[#F36B21]/50 group-hover:border-[#F36B21] transition-all flex items-center justify-center bg-[#102B4E]">
              <Shield className="w-5 h-5 text-[#F36B21]" />
            </div>
            <div>
              <div className="flex items-center gap-1.5 leading-tight">
                <span className="font-bold text-white text-base tracking-tight">Jan</span>
                <span className="font-bold text-[#F36B21] text-base tracking-tight">Sakshi</span>
                <span className="text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded bg-white/10 text-white/80 ml-1">
                  Authority
                </span>
              </div>
              <p className="text-[10px] text-white/50 tracking-wider font-mono">Civic Decision Desk</p>
            </div>
          </Link>

          {/* Navigation Links */}
          <nav className="hidden md:flex items-center gap-1 bg-white/5 p-1 rounded-xl border border-white/5">
            {navItems.map((item) => {
              const Icon = item.icon
              const isActive = location.pathname === item.path
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                    isActive
                      ? 'bg-[#F36B21] text-white shadow-md shadow-[#F36B21]/20'
                      : 'text-white/70 hover:text-white hover:bg-white/5'
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  <span>{item.label}</span>
                </Link>
              )
            })}
          </nav>
        </div>

        {/* User Identity & Logout */}
        <div className="flex items-center gap-3">
          {user && (
            <div className="hidden sm:flex items-center gap-2.5 bg-white/5 border border-white/10 rounded-xl px-3 py-1.5">
              <div className="w-7 h-7 rounded-full bg-[#102B4E] border border-white/20 flex items-center justify-center text-white text-xs font-bold">
                {user.full_name?.charAt(0) || 'U'}
              </div>
              <div className="text-left text-xs leading-snug">
                <p className="font-medium text-white max-w-[120px] truncate">{user.full_name}</p>
                <div className="flex items-center gap-1 mt-0.5">
                  <span className={`text-[9px] px-1.5 py-0.2 rounded border font-mono ${roleInfo.color}`}>
                    {roleInfo.label}
                  </span>
                  {user.department_code && (
                    <span className="text-[9px] px-1.5 py-0.2 rounded border bg-emerald-500/20 text-emerald-300 border-emerald-500/30 font-mono">
                      {user.department_code}
                    </span>
                  )}
                </div>
              </div>
            </div>
          )}

          <button
            onClick={handleLogout}
            title="Sign out of Authority Portal"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-red-400 bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 transition-all cursor-pointer"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Logout</span>
          </button>
        </div>
      </div>
    </header>
  )
}

