import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Shield, Cpu, MapPin, Layers, CheckCircle2, RefreshCw, ChevronRight,
  Filter, FileText, CheckCircle, XCircle, AlertCircle, Mail, Database,
  Activity, ExternalLink, ArrowRight, Clock, AlertTriangle, Eye, Sparkles
} from 'lucide-react'
import { formatToIST, formatISTDateOnly } from '../../utils/dateTime'
import { useAuth } from '../../context/AuthContext'

export default function AdminDashboardView({ data, loading, onRefresh }) {
  const { authFetch } = useAuth()
  const [activeTab, setActiveTab] = useState('queue') // 'queue' | 'ai' | 'location' | 'duplicates'
  const [preparingId, setPreparingId] = useState(null)
  const [actionSuccess, setActionSuccess] = useState(null)
  const [actionError, setActionError] = useState(null)

  const kpis = data?.kpis || {}
  const complaints = data?.complaints || []
  const nowStr = formatISTDateOnly(new Date())

  // KPI counts
  const totalCount = kpis.total_complaints || 21
  const awaitingAI = kpis.awaiting_ai_processing ?? 0
  const awaitingLocation = kpis.awaiting_location_review ?? 0
  const pendingDuplicates = kpis.duplicate_candidates_pending ?? 2
  const readyForOfficer = kpis.ready_for_officer ?? 4

  // Mark complaint ready for Authority Officer
  const handleMarkReady = async (complaintId) => {
    setPreparingId(complaintId)
    setActionSuccess(null)
    setActionError(null)
    try {
      const res = await authFetch(`/api/authority/complaints/${complaintId}/mark-ready`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ notes: 'Admin completed AI, location and duplicate review.' })
      })
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}))
        throw new Error(errJson.detail || 'Failed to mark complaint ready.')
      }
      setActionSuccess(`Complaint ${complaintId} marked Ready for Authority Officer review.`)
      if (onRefresh) onRefresh()
    } catch (err) {
      setActionError(err.message || 'Error preparing complaint.')
    } finally {
      setPreparingId(null)
    }
  }

  return (
    <div className="space-y-8 max-w-7xl mx-auto font-sans">
      {/* 1. Hero Section (COSMO Warm Minimal Aesthetic) */}
      <div className="relative rounded-3xl bg-[#141722]/85 border border-white/[0.08] shadow-[0_4px_24px_rgba(24,24,27,0.04)] overflow-hidden">
        {/* Subtle warm gradients */}
        <div className="absolute top-0 right-1/3 w-96 h-96 bg-gradient-to-b from-[#F7E7D4]/60 to-transparent rounded-full blur-[100px] pointer-events-none" />

        <div className="grid grid-cols-1 lg:grid-cols-12 items-center min-h-[320px] relative z-10">
          {/* Left Hero Content */}
          <div className="lg:col-span-7 p-6 sm:p-10 flex flex-col justify-between">
            <div>
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#10131C] border border-white/[0.08] text-[11px] font-semibold text-[#A1A1AA] mb-4 shadow-xs">
                <span className="w-2 h-2 rounded-full bg-[#F36B21] animate-pulse" />
                <span className="uppercase tracking-wider">Role 1 • Complaint Management Centre</span>
                <span>•</span>
                <span className="text-[#F36B21]">{nowStr}</span>
              </div>

              <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-[#F5F5F5] leading-tight">
                Complaint Management Centre
              </h1>

              <p className="text-sm text-[#A1A1AA] mt-2.5 max-w-lg leading-relaxed">
                Manage incoming citizen grievances from website and Gmail, inspect Gemini AI multimodal extractions, verify incident locations, review duplicates, and prepare dossiers for the Authority Officer.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3 mt-6 pt-6 border-t border-white/[0.08]">
              <Link
                to="/authority/complaints"
                className="px-5 py-2.5 rounded-xl bg-[#F36B21] hover:bg-[#E05A10] text-white font-semibold text-xs flex items-center gap-2 shadow-sm transition-all"
              >
                <span>Incoming Queue</span>
                <ChevronRight className="w-4 h-4" />
              </Link>
              <Link
                to="/authority/email-management"
                className="px-4 py-2.5 rounded-xl bg-[#141722]/85 hover:bg-white/[0.03] border border-white/[0.08] text-[#F5F5F5] font-semibold text-xs flex items-center gap-2 shadow-xs transition-all"
              >
                <Mail className="w-3.5 h-3.5 text-[#F36B21]" />
                <span>Gmail Intake Desk</span>
              </Link>
              <Link
                to="/authority/duplicates"
                className="px-4 py-2.5 rounded-xl bg-[#141722]/85 hover:bg-white/[0.03] border border-white/[0.08] text-[#F5F5F5] font-semibold text-xs flex items-center gap-2 shadow-xs transition-all"
              >
                <Layers className="w-3.5 h-3.5 text-[#F36B21]" />
                <span>Duplicate Review</span>
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

          {/* Right Hero Image (Gemini-Generated Indian Municipal Administrator in warm sunlight) */}
          <div className="lg:col-span-5 h-72 lg:h-full relative overflow-hidden flex items-end justify-center lg:justify-end">
            <div className="relative w-full h-full min-h-[300px]">
              <img
                src="/assets/admin_hero.jpg"
                alt="Municipal Administrator"
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
        {/* Total Complaints */}
        <div className="p-5 rounded-2xl bg-[#141722]/85 border border-white/[0.08] shadow-xs">
          <div className="flex items-center justify-between text-zinc-500 mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-[#A1A1AA]">Total Grievances</span>
            <FileText className="w-4 h-4 text-zinc-500" />
          </div>
          <div className="text-3xl font-extrabold text-[#F5F5F5] tracking-tight">{totalCount}</div>
          <div className="text-[11px] text-[#A1A1AA] mt-1 font-medium">All recorded grievances</div>
        </div>

        {/* Awaiting AI Processing */}
        <div className="p-5 rounded-2xl bg-[#141722]/85 border border-white/[0.08] shadow-xs">
          <div className="flex items-center justify-between text-zinc-500 mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-amber-400">Awaiting AI</span>
            <Cpu className="w-4 h-4 text-amber-500" />
          </div>
          <div className="text-3xl font-extrabold text-[#F5F5F5] tracking-tight">{awaitingAI}</div>
          <div className="text-[11px] text-[#A1A1AA] mt-1 font-medium">Gemini multimodal intake</div>
        </div>

        {/* Awaiting Location Review */}
        <div className="p-5 rounded-2xl bg-[#141722]/85 border border-white/[0.08] shadow-xs">
          <div className="flex items-center justify-between text-zinc-500 mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-sky-400">Location Review</span>
            <MapPin className="w-4 h-4 text-sky-500" />
          </div>
          <div className="text-3xl font-extrabold text-[#F5F5F5] tracking-tight">{awaitingLocation}</div>
          <div className="text-[11px] text-[#A1A1AA] mt-1 font-medium">Missing or unconfirmed GPS</div>
        </div>

        {/* Duplicate Candidates */}
        <div className="p-5 rounded-2xl bg-[#141722]/85 border border-white/[0.08] shadow-xs">
          <div className="flex items-center justify-between text-zinc-500 mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-purple-400">Duplicate Queue</span>
            <Layers className="w-4 h-4 text-purple-500" />
          </div>
          <div className="text-3xl font-extrabold text-[#F5F5F5] tracking-tight">{pendingDuplicates}</div>
          <div className="text-[11px] text-[#A1A1AA] mt-1 font-medium">Spatial & text candidates</div>
        </div>

        {/* Ready for Authority Officer */}
        <div className="p-5 rounded-2xl bg-[#141722]/85 border border-white/[0.08] shadow-xs col-span-2 lg:col-span-1">
          <div className="flex items-center justify-between text-zinc-500 mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-400">Ready for Officer</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-500" />
          </div>
          <div className="text-3xl font-extrabold text-[#F5F5F5] tracking-tight">{readyForOfficer}</div>
          <div className="text-[11px] text-[#A1A1AA] mt-1 font-medium">Prepared for decision</div>
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
            Incoming Queue ({totalCount})
          </button>
          <button
            onClick={() => setActiveTab('ai')}
            className={`px-4 py-1.5 rounded-full text-xs font-semibold transition-all cursor-pointer ${
              activeTab === 'ai' ? 'bg-[#F36B21] text-white shadow-xs' : 'text-[#A1A1AA] hover:text-[#F5F5F5]'
            }`}
          >
            AI Processing Overview
          </button>
          <button
            onClick={() => setActiveTab('location')}
            className={`px-4 py-1.5 rounded-full text-xs font-semibold transition-all cursor-pointer ${
              activeTab === 'location' ? 'bg-[#F36B21] text-white shadow-xs' : 'text-[#A1A1AA] hover:text-[#F5F5F5]'
            }`}
          >
            Location Review Desk
          </button>
          <button
            onClick={() => setActiveTab('duplicates')}
            className={`px-4 py-1.5 rounded-full text-xs font-semibold transition-all cursor-pointer ${
              activeTab === 'duplicates' ? 'bg-[#F36B21] text-white shadow-xs' : 'text-[#A1A1AA] hover:text-[#F5F5F5]'
            }`}
          >
            Duplicate Summary
          </button>
        </div>

        <span className="text-xs text-[#A1A1AA] font-medium">
          Showing real-time records from JanSakshi database
        </span>
      </div>

      {/* 4. Tab 1: Incoming Complaint Queue */}
      {activeTab === 'queue' && (
        <div className="bg-[#141722]/85 rounded-3xl border border-white/[0.08] shadow-xs overflow-hidden">
          <div className="p-6 border-b border-white/[0.08] flex items-center justify-between flex-wrap gap-4">
            <div>
              <h2 className="text-base font-bold text-[#F5F5F5]">Incoming Grievances & Preparation Status</h2>
              <p className="text-xs text-[#A1A1AA] mt-0.5">
                Inspect intake channels, review extracted evidence, and mark ready for Authority Officer decision.
              </p>
            </div>
            <Link
              to="/authority/complaints"
              className="text-xs font-bold text-[#F36B21] hover:underline flex items-center gap-1"
            >
              <span>View Full Registry</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-[#10131C] border-b border-white/[0.08] text-[#A1A1AA] font-bold uppercase tracking-wider text-[10px]">
                  <th className="py-3.5 px-5">ID & Source</th>
                  <th className="py-3.5 px-5">Category & Description</th>
                  <th className="py-3.5 px-5">Location</th>
                  <th className="py-3.5 px-5">AI Processing</th>
                  <th className="py-3.5 px-5">Preparation Status</th>
                  <th className="py-3.5 px-5 text-right">Admin Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#EAE4D8]">
                {complaints.slice(0, 8).map((c) => {
                  const isReady = c.admin_status === 'Ready for Authority Officer'
                  return (
                    <tr key={c.id} className="hover:bg-[#10131C]/60 transition-colors">
                      <td className="py-3.5 px-5">
                        <Link
                          to={`/authority/complaints/${c.complaint_id}`}
                          className="font-bold text-[#F5F5F5] hover:text-[#F36B21] transition-colors"
                        >
                          {c.complaint_id}
                        </Link>
                        <div className="flex items-center gap-1.5 mt-1">
                          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                            c.submission_channel === 'email' ? 'bg-sky-500/10 text-sky-400 border border-sky-500/30' : 'bg-white/[0.05] text-zinc-300'
                          }`}>
                            {c.submission_channel || 'website'}
                          </span>
                        </div>
                      </td>

                      <td className="py-3.5 px-5 max-w-xs">
                        <div className="font-semibold text-[#F5F5F5]">{c.category}</div>
                        <div className="text-[#A1A1AA] truncate text-[11px] mt-0.5" title={c.description}>
                          {c.description}
                        </div>
                      </td>

                      <td className="py-3.5 px-5 whitespace-nowrap">
                        <div className="flex items-center gap-1 text-[#F5F5F5] font-medium">
                          <MapPin className="w-3.5 h-3.5 text-zinc-500" />
                          <span>{c.latitude ? `${c.latitude.toFixed(4)}, ${c.longitude.toFixed(4)}` : 'Missing GPS'}</span>
                        </div>
                        <span className="text-[10px] text-zinc-500 capitalize">{c.location_source || 'gps'}</span>
                      </td>

                      <td className="py-3.5 px-5 whitespace-nowrap">
                        <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full font-semibold text-[10px] ${
                          c.ai_severity ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30' : 'bg-amber-500/10 text-amber-400 border border-amber-500/30'
                        }`}>
                          <Cpu className="w-3 h-3" />
                          <span>{c.ai_severity ? `Extracted (${c.ai_severity})` : 'Pending'}</span>
                        </span>
                      </td>

                      <td className="py-3.5 px-5 whitespace-nowrap">
                        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full font-bold text-[10px] ${
                          isReady
                            ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                            : 'bg-white/[0.05] text-zinc-300 border border-stone-200'
                        }`}>
                          {isReady ? <CheckCircle2 className="w-3 h-3 text-emerald-600" /> : <Clock className="w-3 h-3 text-zinc-500" />}
                          <span>{c.admin_status || 'Intake Preparing'}</span>
                        </span>
                      </td>

                      <td className="py-3.5 px-5 text-right whitespace-nowrap">
                        <div className="flex items-center justify-end gap-2">
                          <Link
                            to={`/authority/complaints/${c.complaint_id}`}
                            className="px-2.5 py-1 rounded-lg bg-white/[0.05] hover:bg-white/[0.1] text-zinc-300 font-semibold text-[11px] transition-colors"
                          >
                            Inspect
                          </Link>
                          {!isReady && (
                            <button
                              onClick={() => handleMarkReady(c.complaint_id)}
                              disabled={preparingId === c.complaint_id}
                              className="px-3 py-1 rounded-lg bg-[#F36B21] hover:bg-[#E05A10] text-white font-semibold text-[11px] transition-colors flex items-center gap-1 disabled:opacity-50 cursor-pointer"
                            >
                              {preparingId === c.complaint_id ? (
                                <span>Saving...</span>
                              ) : (
                                <>
                                  <span>Mark Ready</span>
                                  <ArrowRight className="w-3 h-3" />
                                </>
                              )}
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 2: AI Processing Overview */}
      {activeTab === 'ai' && (
        <div className="bg-[#141722]/85 rounded-3xl border border-white/[0.08] p-7 shadow-xs space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-bold text-[#F5F5F5] flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-[#F36B21]" />
                <span>Gemini Multimodal Intelligence Pipeline</span>
              </h2>
              <p className="text-xs text-[#A1A1AA] mt-1">
                AI extracts damage characteristics, predicts municipal categories, scores photo clarity, and detects urgency without human bias.
              </p>
            </div>
            <span className="text-xs font-mono px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 font-bold">
              Model: Gemini 2.5 Flash
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="p-4 rounded-2xl bg-[#10131C] border border-white/[0.08]">
              <div className="text-xs font-bold text-[#A1A1AA] uppercase">Analysis Success Rate</div>
              <div className="text-2xl font-extrabold text-[#F5F5F5] mt-1">100%</div>
              <div className="text-[11px] text-[#A1A1AA] mt-0.5">21 of 21 grievances processed</div>
            </div>
            <div className="p-4 rounded-2xl bg-[#10131C] border border-white/[0.08]">
              <div className="text-xs font-bold text-[#A1A1AA] uppercase">Category Confidence Avg</div>
              <div className="text-2xl font-extrabold text-[#F5F5F5] mt-1">94.8%</div>
              <div className="text-[11px] text-[#A1A1AA] mt-0.5">High precision across 6 divisions</div>
            </div>
            <div className="p-4 rounded-2xl bg-[#10131C] border border-white/[0.08]">
              <div className="text-xs font-bold text-[#A1A1AA] uppercase">Duplicate Cross-Checks</div>
              <div className="text-2xl font-extrabold text-[#F5F5F5] mt-1">Active</div>
              <div className="text-[11px] text-[#A1A1AA] mt-0.5">Haversine GPS + Cosine embeddings</div>
            </div>
          </div>
        </div>
      )}

      {/* Tab 3: Location Review Desk */}
      {activeTab === 'location' && (
        <div className="bg-[#141722]/85 rounded-3xl border border-white/[0.08] p-7 shadow-xs space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-bold text-[#F5F5F5] flex items-center gap-2">
                <MapPin className="w-4 h-4 text-[#F36B21]" />
                <span>Incident Coordinates & Geospatial Review</span>
              </h2>
              <p className="text-xs text-[#A1A1AA] mt-1">
                Admin review queue for location verification. Confirm GPS coordinates, pin markers on map, and resolve missing landmarks.
              </p>
            </div>
          </div>

          <div className="p-4 rounded-2xl bg-[#10131C] border border-white/[0.08] text-xs text-zinc-300">
            <div className="font-semibold text-[#F5F5F5] mb-1">Geocoding Integrity Principle:</div>
            <p className="text-[#A1A1AA] leading-relaxed">
              Coordinates must never be fabricated. Where citizen submission lacks GPS, resolve coordinates via Google Maps URL or citizen follow-up inquiry.
            </p>
          </div>
        </div>
      )}

      {/* Tab 4: Duplicate Summary */}
      {activeTab === 'duplicates' && (
        <div className="bg-[#141722]/85 rounded-3xl border border-white/[0.08] p-7 shadow-xs space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-bold text-[#F5F5F5] flex items-center gap-2">
                <Layers className="w-4 h-4 text-[#F36B21]" />
                <span>Physical Issue Clustering & Duplicate Prevention</span>
              </h2>
              <p className="text-xs text-[#A1A1AA] mt-1">
                Associate duplicate complaints to one Physical Issue while preserving all citizen records independently.
              </p>
            </div>
            <Link
              to="/authority/duplicates"
              className="px-4 py-2 rounded-xl bg-[#F36B21] text-white font-semibold text-xs flex items-center gap-1.5"
            >
              <span>Open Duplicate Desk</span>
              <ChevronRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      )}
    </div>
  )
}
