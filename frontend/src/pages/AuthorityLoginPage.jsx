import React, { useState } from 'react'
import { useNavigate, Link, useSearchParams } from 'react-router-dom'
import {
  Lock, User, ArrowRight, AlertCircle, CheckCircle,
  Sparkles, ChevronDown, ChevronUp, Eye, EyeOff,
  Cpu, CheckCircle2, Wrench, Shield, Clock
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'

export default function AuthorityLoginPage() {
  const [searchParams] = useSearchParams()
  const sessionExpired = searchParams.get('session_expired') === 'true'
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState(null)
  const [demoExpanded, setDemoExpanded] = useState(false)
  const { login, loading } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    const result = await login(username, password)
    if (result.success) {
      if (result.user.role === 'department_officer') {
        const authorized = result.user.authorized_departments || []
        if (result.user.has_all_departments || authorized.length > 1) {
          navigate('/authority/select-department')
        } else {
          const singleDept = authorized[0] || result.user.department_id || 1
          localStorage.setItem('jansakshi_active_dept_id', singleDept.toString())
          localStorage.setItem('jansakshi_active_dept_code', result.user.department_code || 'RPW')
          navigate(`/authority?dept=${singleDept}`)
        }
      } else {
        navigate('/authority')
      }
    } else {
      setError(result.error || 'Authentication failed. Please verify credentials.')
    }
  }

  const fillCredentials = (accountType) => {
    if (accountType === 'admin') {
      setUsername('admin')
    } else if (accountType === 'officer') {
      setUsername('officer')
    } else if (accountType === 'dept_demo') {
      setUsername('dept_demo')
    }
    setPassword('')
    setError(null)
  }

  return (
    <div className="min-h-screen bg-[#090B10] text-[#F5F5F5] flex flex-col lg:flex-row antialiased font-sans selection:bg-[#F36B21] selection:text-white relative overflow-x-hidden">
      {/* Saffron & Deep Navy Ambient Glow */}
      <div className="fixed top-0 right-1/4 w-[600px] h-[500px] bg-gradient-to-b from-[#F36B21]/10 via-[#102B4E]/15 to-transparent rounded-full blur-[140px] pointer-events-none z-0" />
      <div className="fixed -bottom-20 -right-20 w-[450px] h-[450px] bg-[#102B4E]/25 rounded-full blur-[160px] pointer-events-none z-0" />

      {/* ========================================================================= */}
      {/* LEFT COLUMN: CINEMATIC BRAND VISUAL EXPERIENCE (55% - 60% Desktop)        */}
      {/* ========================================================================= */}
      <div className="relative w-full lg:w-[58%] xl:w-[60%] min-h-[380px] lg:min-h-screen flex flex-col justify-between p-6 sm:p-10 xl:p-14 overflow-hidden border-b lg:border-b-0 lg:border-r border-white/[0.08] z-10">
        {/* Background Hero Image */}
        <div className="absolute inset-0 z-0">
          <img
            src="/assets/staff_login_hero.jpg"
            alt="JanSakshi Smart City Civic Operations"
            className="w-full h-full object-cover object-center transform scale-105 transition-transform duration-1000 ease-out"
          />
          {/* Cinematic Vignette Gradients */}
          <div className="absolute inset-0 bg-gradient-to-t from-[#090B10] via-[#090B10]/60 to-[#090B10]/30" />
          <div className="absolute inset-0 bg-gradient-to-r from-[#090B10]/80 via-transparent to-[#090B10]/90 hidden lg:block" />
          <div className="absolute inset-0 bg-[#102B4E]/20 mix-blend-multiply" />
        </div>

        {/* Top Branding Strip */}
        <div className="relative z-10 flex items-center justify-between">
          <Link to="/" className="inline-flex items-center gap-3 group">
            <div className="w-12 h-12 rounded-full overflow-hidden border-2 border-[#F36B21]/50 group-hover:border-[#F36B21] shadow-lg shadow-[#F36B21]/20 group-hover:scale-105 transition-all flex items-center justify-center bg-black/40">
              <img
                src="/assets/jansakshi-logo.jpg"
                alt="JanSakshi Logo"
                className="w-full h-full object-cover"
              />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-extrabold text-lg tracking-tight text-[#F5F5F5]">Jan</span>
                <span className="font-extrabold text-lg tracking-tight text-[#F36B21]">Sakshi</span>
                <span className="text-[9px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-[#F36B21]/15 text-[#F36B21] border border-[#F36B21]/30">
                  Authority
                </span>
              </div>
              <p className="text-[10px] uppercase font-bold tracking-widest text-[#A1A1AA]/80 mt-0.5">
                Municipal Operations Platform
              </p>
            </div>
          </Link>

          <div className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-white/[0.05] border border-white/[0.08] backdrop-blur-md text-[11px] font-medium text-[#A1A1AA]">
            <span className="w-2 h-2 rounded-full bg-[#138A4B] animate-pulse" />
            <span>Civic Grid Active</span>
          </div>
        </div>

        {/* Hero Middle Content: Editorial Headline & Subtitle */}
        <div className="relative z-10 my-auto py-8 lg:py-0 max-w-xl">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#F36B21]/10 border border-[#F36B21]/25 text-[#F36B21] text-[11px] font-bold tracking-wide uppercase mb-4 backdrop-blur-md">
            <Shield className="w-3.5 h-3.5" />
            <span>Staff & Authority Portal</span>
          </div>

          <h1 className="text-3xl sm:text-4xl xl:text-5xl font-extrabold text-[#F5F5F5] tracking-tight leading-[1.15] mb-4 drop-shadow-md">
            Intelligent Governance. <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-[#F36B21] via-amber-400 to-[#F5F5F5]">
              Accountable Action.
            </span>
          </h1>

          <p className="text-sm sm:text-base text-[#A1A1AA] leading-relaxed font-normal max-w-lg">
            One platform. Every complaint. Every resolution. Empowering municipal administrators, authority officers, and field engineers.
          </p>
        </div>

        {/* Bottom Compact Role Indicators */}
        <div className="relative z-10 pt-4 border-t border-white/[0.08] flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-2 sm:gap-3 text-xs font-semibold text-[#A1A1AA]">
            <span className="flex items-center gap-1.5 text-[#F5F5F5]">
              <span className="w-1.5 h-1.5 rounded-full bg-red-400" />
              <span>Admin</span>
            </span>
            <span className="text-white/20">·</span>
            <span className="flex items-center gap-1.5 text-[#F5F5F5]">
              <span className="w-1.5 h-1.5 rounded-full bg-[#F36B21]" />
              <span>Authority Officer</span>
            </span>
            <span className="text-white/20">·</span>
            <span className="flex items-center gap-1.5 text-[#F5F5F5]">
              <span className="w-1.5 h-1.5 rounded-full bg-sky-400" />
              <span>Department Officer</span>
            </span>
          </div>

          <span className="text-[11px] text-[#A1A1AA]/70 font-mono">
            v7.0 • Civic Operations
          </span>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* RIGHT COLUMN: REFINED LOGIN EXPERIENCE (40% - 45% Desktop)                */}
      {/* ========================================================================= */}
      <div className="w-full lg:w-[42%] xl:w-[40%] flex flex-col justify-center items-center p-6 sm:p-10 xl:p-12 relative z-10">
        <div className="w-full max-w-md space-y-6">
          {/* Header Title & Role Strip */}
          <div className="text-left space-y-2">
            <h2 className="text-2xl font-bold tracking-tight text-[#F5F5F5]">
              Welcome to JanSakshi
            </h2>
            <p className="text-xs text-[#A1A1AA]">
              Secure authentication for authorized municipal personnel.
            </p>

            {/* Subtle Role Identity Strip */}
            <div className="inline-flex items-center gap-2 p-1 rounded-xl bg-[#141722]/80 border border-white/[0.08] text-[11px] font-semibold text-[#A1A1AA] mt-1">
              <span className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-white/[0.05] text-[#F5F5F5]">
                <Cpu className="w-3 h-3 text-[#F36B21]" />
                <span>Admin</span>
              </span>
              <span className="text-white/20">|</span>
              <span className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-white/[0.05] text-[#F5F5F5]">
                <CheckCircle2 className="w-3 h-3 text-[#138A4B]" />
                <span>Officer</span>
              </span>
              <span className="text-white/20">|</span>
              <span className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-white/[0.05] text-[#F5F5F5]">
                <Wrench className="w-3 h-3 text-sky-400" />
                <span>Department</span>
              </span>
            </div>
          </div>

          {/* Login Card Panel */}
          <div className="bg-[#141722]/85 backdrop-blur-xl border border-white/[0.08] rounded-3xl p-6 sm:p-8 shadow-2xl space-y-5">
            {sessionExpired && !error && (
              <div className="p-3.5 rounded-2xl bg-amber-500/10 border border-amber-500/30 flex items-center gap-2.5 text-amber-300 text-xs">
                <Clock className="w-4 h-4 flex-shrink-0 text-amber-400" />
                <span>Your municipal staff session has expired. Please sign in to resume operations.</span>
              </div>
            )}

            {error && (
              <div className="p-3.5 rounded-2xl bg-red-500/10 border border-red-500/30 flex items-center gap-2.5 text-red-400 text-xs">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Username Field */}
              <div>
                <label className="block text-xs font-semibold text-[#A1A1AA] mb-1.5 uppercase tracking-wider">
                  Staff Username
                </label>
                <div className="relative">
                  <User className="w-4 h-4 text-[#A1A1AA] absolute left-3.5 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    required
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="e.g. officer, admin, dept_demo"
                    className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-[#10131C] border border-white/[0.08] text-sm text-[#F5F5F5] placeholder-[#A1A1AA]/40 focus:outline-none focus:ring-2 focus:ring-[#F36B21]/40 focus:border-[#F36B21] transition-all font-medium"
                  />
                </div>
              </div>

              {/* Password Field with Show/Hide Toggle */}
              <div>
                <label className="block text-xs font-semibold text-[#A1A1AA] mb-1.5 uppercase tracking-wider">
                  Password
                </label>
                <div className="relative">
                  <Lock className="w-4 h-4 text-[#A1A1AA] absolute left-3.5 top-1/2 -translate-y-1/2" />
                  <input
                    type={showPassword ? 'text' : 'password'}
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••••••"
                    className="w-full pl-10 pr-10 py-2.5 rounded-xl bg-[#10131C] border border-white/[0.08] text-sm text-[#F5F5F5] placeholder-[#A1A1AA]/40 focus:outline-none focus:ring-2 focus:ring-[#F36B21]/40 focus:border-[#F36B21] transition-all font-mono"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3.5 top-1/2 -translate-y-1/2 text-[#A1A1AA] hover:text-[#F5F5F5] transition-colors cursor-pointer"
                    title={showPassword ? 'Hide password' : 'Show password'}
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              {/* Submit Button */}
              <button
                type="submit"
                disabled={loading}
                className="w-full py-3 rounded-xl bg-[#F36B21] hover:bg-[#E05A10] text-white font-semibold text-sm flex items-center justify-center gap-2 shadow-lg shadow-[#F36B21]/20 transition-all cursor-pointer disabled:opacity-50 mt-3"
              >
                {loading ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    <span>Authenticating...</span>
                  </>
                ) : (
                  <>
                    <span>Sign In to Operations</span>
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </form>

            {/* Collapsible Hackathon Demo Access (Development Mode Only) */}
            {import.meta.env.DEV && (
              <div className="pt-4 border-t border-white/[0.08]">
                <button
                  type="button"
                  onClick={() => setDemoExpanded(!demoExpanded)}
                  className="w-full flex items-center justify-between text-xs font-semibold text-[#A1A1AA] hover:text-[#F5F5F5] transition-colors py-1 cursor-pointer"
                >
                  <span className="flex items-center gap-1.5 uppercase tracking-wider text-[11px]">
                    <Sparkles className="w-3.5 h-3.5 text-[#F36B21]" />
                    Hackathon Demo Access
                  </span>
                  {demoExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </button>

                {demoExpanded && (
                  <div className="mt-3 space-y-2">
                    {/* Option 1: Admin */}
                    <div
                      onClick={() => fillCredentials('admin')}
                      className={`p-3 rounded-2xl border text-left cursor-pointer transition-all flex items-center justify-between ${
                        username === 'admin'
                          ? 'bg-[#191D2A] text-white border-[#F36B21]/50 shadow-sm'
                          : 'bg-[#10131C] hover:bg-[#191D2A]/60 text-[#A1A1AA] border-white/[0.08]'
                      }`}
                    >
                      <div className="flex items-center gap-2.5">
                        <div className="w-8 h-8 rounded-xl bg-red-500/10 border border-red-500/20 flex items-center justify-center text-red-400 flex-shrink-0">
                          <Cpu className="w-4 h-4" />
                        </div>
                        <div>
                          <div className="text-xs font-bold text-[#F5F5F5] flex items-center gap-1.5">
                            <span>Admin</span>
                            <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-white/[0.08] text-[#A1A1AA]">
                              admin
                            </span>
                          </div>
                          <div className="text-[11px] text-[#A1A1AA]">
                            AI & Complaint Management
                          </div>
                        </div>
                      </div>
                      {username === 'admin' && <CheckCircle className="w-4 h-4 text-[#F36B21]" />}
                    </div>

                    {/* Option 2: Authority Officer */}
                    <div
                      onClick={() => fillCredentials('officer')}
                      className={`p-3 rounded-2xl border text-left cursor-pointer transition-all flex items-center justify-between ${
                        username === 'officer'
                          ? 'bg-[#191D2A] text-white border-[#F36B21]/50 shadow-sm'
                          : 'bg-[#10131C] hover:bg-[#191D2A]/60 text-[#A1A1AA] border-white/[0.08]'
                      }`}
                    >
                      <div className="flex items-center gap-2.5">
                        <div className="w-8 h-8 rounded-xl bg-[#F36B21]/10 border border-[#F36B21]/20 flex items-center justify-center text-[#F36B21] flex-shrink-0">
                          <CheckCircle2 className="w-4 h-4" />
                        </div>
                        <div>
                          <div className="text-xs font-bold text-[#F5F5F5] flex items-center gap-1.5">
                            <span>Authority Officer</span>
                            <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-white/[0.08] text-[#A1A1AA]">
                              officer
                            </span>
                          </div>
                          <div className="text-[11px] text-[#A1A1AA]">
                            Decisions & Department Assignment
                          </div>
                        </div>
                      </div>
                      {username === 'officer' && <CheckCircle className="w-4 h-4 text-[#F36B21]" />}
                    </div>

                    {/* Option 3: Department Officer */}
                    <div
                      onClick={() => fillCredentials('dept_demo')}
                      className={`p-3 rounded-2xl border text-left cursor-pointer transition-all flex items-center justify-between ${
                        username === 'dept_demo'
                          ? 'bg-[#191D2A] text-white border-[#F36B21]/50 shadow-sm'
                          : 'bg-[#10131C] hover:bg-[#191D2A]/60 text-[#A1A1AA] border-white/[0.08]'
                      }`}
                    >
                      <div className="flex items-center gap-2.5">
                        <div className="w-8 h-8 rounded-xl bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400 flex-shrink-0">
                          <Wrench className="w-4 h-4" />
                        </div>
                        <div>
                          <div className="text-xs font-bold text-[#F5F5F5] flex items-center gap-1.5">
                            <span>Department Officer</span>
                            <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-white/[0.08] text-[#A1A1AA]">
                              dept_demo
                            </span>
                          </div>
                          <div className="text-[11px] text-[#A1A1AA]">
                            All Six Department Workspaces
                          </div>
                        </div>
                      </div>
                      {username === 'dept_demo' && <CheckCircle className="w-4 h-4 text-[#F36B21]" />}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Return link to Citizen Portal */}
          <div className="text-center pt-2">
            <Link
              to="/"
              className="text-xs text-[#A1A1AA] hover:text-[#F5F5F5] transition-colors inline-flex items-center gap-1.5 font-medium"
            >
              ← Back to Citizen Grievance Portal
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
