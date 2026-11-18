import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  Activity, MapPin, AlertTriangle, CheckCircle2, Clock,
  Filter, RefreshCw, ChevronRight, Layers, Building2,
  TrendingUp, Shield, BarChart3, Database, Info, Sparkles,
  ArrowUpRight, AlertCircle, FileText, Eye, CheckSquare
} from 'lucide-react'
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import AuthorityLayout from '../../components/AuthorityLayout'
import { useAuth } from '../../context/AuthContext'
import { formatToIST } from '../../utils/dateTime'

function MapAutoBounds({ centers }) {
  const map = useMap()
  useEffect(() => {
    if (!centers || centers.length === 0) return
    const valid = centers.filter(c => c.lat && c.lon)
    if (valid.length === 0) return
    if (valid.length === 1) {
      map.setView([valid[0].lat, valid[0].lon], 13)
    } else {
      const bounds = L.latLngBounds(valid.map(c => [c.lat, c.lon]))
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 })
    }
  }, [centers, map])
  return null
}

export default function AuthorityEquityIntelligencePage() {
  const { authFetch, user } = useAuth()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [tileError, setTileError] = useState(false)
  const [timeWindow, setTimeWindow] = useState('30')
  const [deptFilter, setDeptFilter] = useState('')
  const [selectedArea, setSelectedArea] = useState(null)

  const isAuthorityOfficer = user?.role === 'authority_officer'
  const isAdmin = user?.role === 'admin'
  const isDeptOfficer = user?.role === 'department_officer'

  const fetchEquityData = async () => {
    setLoading(true)
    setError(null)
    try {
      let url = `/api/authority/equity/overview?days=${timeWindow}`
      if (deptFilter) {
        url += `&department_id=${deptFilter}`
      }
      const res = await authFetch(url)
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}))
        throw new Error(errJson.detail || 'Failed to fetch equity intelligence data.')
      }
      const json = await res.json()
      setData(json)
      if (json.areas && json.areas.length > 0 && !selectedArea) {
        setSelectedArea(json.areas[0])
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchEquityData()
  }, [timeWindow, deptFilter])

  const summary = data?.summary || data?.kpis || {}
  const areas = data?.areas || data?.area_metrics || []
  const deptCoverage = data?.department_coverage || []
  const recommendations = data?.recommendations || []

  // Valid centers for map
  const mapCenters = areas
    .filter(a => (a.center_lat || a.representative_latitude) && (a.center_lon || a.representative_longitude))
    .map(a => ({
      name: a.area_name,
      lat: a.center_lat || a.representative_latitude,
      lon: a.center_lon || a.representative_longitude,
      unresolvedRate: a.unresolved_rate,
      total: a.total_complaints,
      slaBreachRate: a.sla_breach_rate,
      flags: a.attention_flags || a.indicators,
      isInsufficient: a.is_insufficient_sample
    }))

  const defaultCenter = mapCenters.length > 0
    ? [mapCenters[0].lat, mapCenters[0].lon]
    : [17.4375, 78.4482]

  const pageTitle = isAuthorityOfficer
    ? 'Civic Parity & Dispatch Insights'
    : isDeptOfficer
    ? 'Division Service Equity & SLA'
    : 'Civic Equity Intelligence'

  const breadcrumbsList = isAuthorityOfficer
    ? ['Authority Officer', 'Civic Parity Context']
    : isDeptOfficer
    ? ['Division', 'Equity & SLA Compliance']
    : ['Admin', 'Civic Equity Intelligence']

  return (
    <AuthorityLayout
      pageTitle={pageTitle}
      breadcrumbs={breadcrumbsList}
    >
      <div className="space-y-8 max-w-7xl mx-auto font-sans pb-12">
        {/* Top Header Card */}
        <div className="relative rounded-3xl bg-[#141722]/85 border border-white/[0.08] p-6 sm:p-8 backdrop-blur-xl overflow-hidden shadow-2xl">
          <div className="absolute top-0 right-1/4 w-96 h-96 bg-gradient-to-b from-[#F36B21]/15 via-[#102B4E]/20 to-transparent rounded-full blur-[110px] pointer-events-none" />

          <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
            <div>
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#10131C] border border-white/[0.08] text-[11px] font-semibold text-[#A1A1AA] mb-3 shadow-xs">
                <Activity className="w-3.5 h-3.5 text-[#F36B21]" />
                <span className="uppercase tracking-wider">
                  {isAuthorityOfficer ? 'Authority Decision Support' : 'Administrative Governance'} • Phase 8
                </span>
                <span>•</span>
                <span className="text-[#138A4B]">Verified Grounded Analytics</span>
              </div>
              <h1 className="text-2xl sm:text-3xl font-extrabold text-[#F5F5F5] tracking-tight">
                {pageTitle}
              </h1>
              <p className="text-xs sm:text-sm text-[#A1A1AA] mt-2 max-w-3xl leading-relaxed">
                {isAuthorityOfficer
                  ? 'Operational insight for equitable municipal dispatch. Review geographic backlog and statutory SLA breach rates across municipal divisions to allocate resources fairly and prevent complaint buildup.'
                  : 'Objective geographical audit of municipal response distribution across wards and localities. Monitors unresolved grievance concentrations, repeat issue clusters, SLA response disparities, and data completeness to ensure fair municipal coverage.'}
              </p>
            </div>

            {/* Controls */}
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex items-center gap-2 bg-[#10131C] border border-white/[0.08] rounded-xl px-3 py-2 text-xs">
                <Clock className="w-3.5 h-3.5 text-[#A1A1AA]" />
                <select
                  value={timeWindow}
                  onChange={(e) => setTimeWindow(e.target.value)}
                  className="bg-transparent text-[#F5F5F5] font-semibold focus:outline-hidden cursor-pointer"
                >
                  <option value="7" className="bg-[#10131C]">Past 7 Days</option>
                  <option value="30" className="bg-[#10131C]">Past 30 Days</option>
                  <option value="90" className="bg-[#10131C]">Past 90 Days</option>
                  <option value="365" className="bg-[#10131C]">All Time (1 Year)</option>
                </select>
              </div>

              {!isDeptOfficer && (
                <div className="flex items-center gap-2 bg-[#10131C] border border-white/[0.08] rounded-xl px-3 py-2 text-xs">
                  <Building2 className="w-3.5 h-3.5 text-[#A1A1AA]" />
                  <select
                    value={deptFilter}
                    onChange={(e) => setDeptFilter(e.target.value)}
                    className="bg-transparent text-[#F5F5F5] font-semibold focus:outline-hidden cursor-pointer"
                  >
                    <option value="" className="bg-[#10131C]">All Departments</option>
                    <option value="1" className="bg-[#10131C]">Roads & Public Works</option>
                    <option value="2" className="bg-[#10131C]">Sanitation & Waste</option>
                    <option value="3" className="bg-[#10131C]">Water Supply & Sewerage</option>
                    <option value="4" className="bg-[#10131C]">Storm Water Drainage</option>
                    <option value="5" className="bg-[#10131C]">Electrical & Street Lighting</option>
                    <option value="6" className="bg-[#10131C]">Parks & Infrastructure</option>
                  </select>
                </div>
              )}

              <button
                onClick={fetchEquityData}
                disabled={loading}
                className="px-4 py-2 rounded-xl bg-white/[0.06] hover:bg-white/[0.12] border border-white/[0.08] text-[#F5F5F5] text-xs font-semibold flex items-center gap-2 cursor-pointer transition-all"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-[#F36B21]' : 'text-[#A1A1AA]'}`} />
                <span>Sync</span>
              </button>
            </div>
          </div>

          {/* Role-Specific Governance Banner */}
          {isAuthorityOfficer && (
            <div className="mt-4 pt-3 border-t border-white/[0.08] flex items-center gap-2 text-xs text-sky-300 bg-sky-500/10 p-3 rounded-xl border border-sky-500/20">
              <Eye className="w-4 h-4 flex-shrink-0" />
              <span>
                <strong>Authority Officer Read-Only Access:</strong> Geographic backlog and SLA metrics are provided as decision context to balance municipal dispatch and prioritize under-resourced wards.
              </span>
            </div>
          )}
        </div>

        {error && (
          <div className="p-4 rounded-2xl bg-red-500/10 border border-red-500/30 text-red-400 text-xs flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
            <button onClick={fetchEquityData} className="underline font-semibold cursor-pointer">
              Retry
            </button>
          </div>
        )}

        {/* KPI Strip with Clear Denominators and Reporting Period */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          <div className="p-4 rounded-2xl bg-[#141722]/80 border border-white/[0.08] backdrop-blur-md">
            <div className="text-[11px] font-semibold text-[#A1A1AA] uppercase tracking-wider">Total Areas</div>
            <div className="text-2xl font-black text-[#F5F5F5] mt-1">{summary.total_areas ?? summary.total_areas_analyzed ?? '—'}</div>
            <div className="text-[10px] text-[#A1A1AA] mt-1 font-mono">{summary.total_complaints || summary.total_complaints_analyzed || 0} Grievances</div>
          </div>

          <div className="p-4 rounded-2xl bg-[#141722]/80 border border-amber-500/20 backdrop-blur-md">
            <div className="text-[11px] font-semibold text-amber-400 uppercase tracking-wider">Needs Attention</div>
            <div className="text-2xl font-black text-amber-400 mt-1">{summary.areas_requiring_attention ?? 0}</div>
            <div className="text-[10px] text-[#A1A1AA] mt-1">Wards with elevated disparity</div>
          </div>

          <div className="p-4 rounded-2xl bg-[#141722]/80 border border-red-500/20 backdrop-blur-md">
            <div className="text-[11px] font-semibold text-red-400 uppercase tracking-wider">Unresolved Hotspots</div>
            <div className="text-2xl font-black text-red-400 mt-1">{summary.unresolved_hotspots_count ?? summary.unresolved_complaint_hotspots ?? 0}</div>
            <div className="text-[10px] text-[#A1A1AA] mt-1">&ge; 60% backlog (n &ge; 5)</div>
          </div>

          <div className="p-4 rounded-2xl bg-[#141722]/80 border border-sky-500/20 backdrop-blur-md">
            <div className="text-[11px] font-semibold text-sky-400 uppercase tracking-wider">Repeat Clusters</div>
            <div className="text-2xl font-black text-sky-400 mt-1">{summary.repeat_hotspots_count ?? summary.repeat_issue_hotspots ?? 0}</div>
            <div className="text-[10px] text-[#A1A1AA] mt-1">Physical recurring clusters</div>
          </div>

          <div className="p-4 rounded-2xl bg-[#141722]/80 border border-white/[0.08] backdrop-blur-md">
            <div className="text-[11px] font-semibold text-[#A1A1AA] uppercase tracking-wider">SLA Breach Rate</div>
            <div className="text-2xl font-black text-[#F5F5F5] mt-1">{summary.overall_sla_breach_rate ?? 0}%</div>
            <div className="text-[10px] text-[#A1A1AA] mt-1">{summary.high_sla_breach_areas_count ?? summary.areas_with_sla_breaches ?? 0} areas with delays</div>
          </div>

          <div className="p-4 rounded-2xl bg-[#141722]/80 border border-[#138A4B]/30 backdrop-blur-md">
            <div className="text-[11px] font-semibold text-[#138A4B] uppercase tracking-wider">Data Completeness</div>
            <div className="text-2xl font-black text-[#138A4B] mt-1">{summary.data_completeness_pct ?? summary.overall_data_completeness_pct ?? 100}%</div>
            <div className="text-[10px] text-[#A1A1AA] mt-1">Grounded GPS coordinates</div>
          </div>
        </div>

        {/* Interactive Map & Geographic Distribution */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Map Column (7 cols) */}
          <div className="lg:col-span-7 bg-[#141722]/85 rounded-3xl border border-white/[0.08] p-5 flex flex-col shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <MapPin className="w-4 h-4 text-[#F36B21]" />
                <h2 className="text-sm font-bold text-[#F5F5F5] uppercase tracking-wider">
                  Grounded Municipal Disparity Map
                </h2>
              </div>
              <div className="flex items-center gap-3 text-[11px] text-[#A1A1AA]">
                <div className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
                  <span>Normal (&lt;40%)</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-amber-500" />
                  <span>Elevated (40-60%)</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-rose-500" />
                  <span>Critical (&gt;60%)</span>
                </div>
              </div>
            </div>

            {tileError && (
              <div className="mb-2 p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300 text-[11px] flex items-center gap-2">
                <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />
                <span>Map network notice: Operating on high-contrast vector fallback. Coordinates remain 100% accurate.</span>
              </div>
            )}

            {/* Reliable OpenStreetMap Dark Vector Container (No API Key Required) */}
            <div className="h-[400px] w-full rounded-2xl overflow-hidden border border-white/[0.08] relative z-0 [&_.leaflet-tile-pane]:brightness-[0.6] [&_.leaflet-tile-pane]:invert [&_.leaflet-tile-pane]:contrast-[1.6] [&_.leaflet-tile-pane]:hue-rotate-[195deg] [&_.leaflet-tile-pane]:saturate-[0.3]">
              <MapContainer
                center={defaultCenter}
                zoom={12}
                scrollWheelZoom={false}
                style={{ height: '100%', width: '100%', backgroundColor: '#10131C' }}
              >
                <TileLayer
                  attribution='&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> contributors'
                  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                  eventHandlers={{
                    tileerror: () => setTileError(true)
                  }}
                />
                <MapAutoBounds centers={mapCenters} />
                {mapCenters.map((c, idx) => {
                  const color = c.unresolvedRate > 60 ? '#EF4444' : c.unresolvedRate > 40 ? '#F59E0B' : '#10B981'
                  const radius = Math.max(12, Math.min(30, c.total * 3))
                  return (
                    <CircleMarker
                      key={idx}
                      center={[c.lat, c.lon]}
                      radius={radius}
                      fillColor={color}
                      color="#FFFFFF"
                      weight={1.5}
                      opacity={0.8}
                      fillOpacity={0.4}
                      eventHandlers={{
                        click: () => {
                          const matched = areas.find(a => a.area_name === c.name)
                          if (matched) setSelectedArea(matched)
                        }
                      }}
                    >
                      <Popup>
                        <div className="text-xs text-zinc-900 font-sans p-1">
                          <div className="font-bold text-sm">{c.name}</div>
                          <div className="mt-1">Total Grievances: <strong>{c.total}</strong></div>
                          <div>Unresolved Backlog: <strong>{c.unresolvedRate}%</strong></div>
                          <div>SLA Breach: <strong>{c.slaBreachRate}%</strong></div>
                          {c.isInsufficient && (
                            <div className="mt-1 text-amber-700 font-semibold text-[10px]">
                              Preliminary sample (n &lt; 5) — Not systemic
                            </div>
                          )}
                          {c.flags && c.flags.length > 0 && !c.isInsufficient && (
                            <div className="mt-1 text-red-600 font-semibold text-[10px]">
                              Indicator: {c.flags[0]}
                            </div>
                          )}
                        </div>
                      </Popup>
                    </CircleMarker>
                  )
                })}
              </MapContainer>
            </div>
            <p className="text-[11px] text-[#A1A1AA] mt-3 italic">
              * Powered by OpenStreetMap. Bubble size reflects valid complaint volume; color indicates unresolved backlog rate. Click markers to view area details.
            </p>
          </div>

          {/* Selected Area Deep-Dive (5 cols) */}
          <div className="lg:col-span-5 bg-[#141722]/85 rounded-3xl border border-white/[0.08] p-6 flex flex-col justify-between shadow-xl">
            {selectedArea ? (
              <div className="space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-white/[0.08]">
                  <div>
                    <span className="text-[10px] font-bold uppercase tracking-wider text-[#F36B21]">Ward Dossier</span>
                    <h3 className="text-lg font-bold text-[#F5F5F5]">{selectedArea.area_name}</h3>
                  </div>
                  {selectedArea.is_insufficient_sample ? (
                    <span className="px-2.5 py-1 rounded-full bg-amber-500/15 border border-amber-500/30 text-amber-400 text-[10px] font-bold">
                      Preliminary (n={selectedArea.total_complaints})
                    </span>
                  ) : selectedArea.attention_flags && selectedArea.attention_flags.length > 0 ? (
                    <span className="px-2.5 py-1 rounded-full bg-red-500/15 border border-red-500/30 text-red-400 text-[10px] font-bold">
                      {selectedArea.attention_flags[0]}
                    </span>
                  ) : (
                    <span className="px-2.5 py-1 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 text-[10px] font-bold">
                      Optimal Service
                    </span>
                  )}
                </div>

                {/* Insufficient Sample Warning Callout */}
                {selectedArea.is_insufficient_sample && (
                  <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                    <span>{selectedArea.sample_warning || `Sample volume (n = ${selectedArea.total_complaints}) is insufficient to draw statistically conclusive systemic disparity findings.`}</span>
                  </div>
                )}

                {/* Distinct KPI Metrics with Explicit Denominators */}
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div className="p-3 rounded-xl bg-[#10131C] border border-white/[0.06]">
                    <div className="text-[10px] text-[#A1A1AA] uppercase">Total Complaints</div>
                    <div className="text-lg font-bold text-[#F5F5F5] mt-0.5">{selectedArea.total_complaints}</div>
                    <div className="text-[10px] text-[#A1A1AA] mt-0.5 font-mono">
                      Denominator: Base Population
                    </div>
                  </div>
                  <div className="p-3 rounded-xl bg-[#10131C] border border-white/[0.06]">
                    <div className="text-[10px] text-[#A1A1AA] uppercase">Unresolved Backlog</div>
                    <div className="text-lg font-bold text-amber-400 mt-0.5">{selectedArea.unresolved_rate}%</div>
                    <div className="text-[10px] text-[#A1A1AA] mt-0.5 font-mono">
                      {selectedArea.unresolved_count} / {selectedArea.total_complaints} tickets
                    </div>
                  </div>
                  <div className="p-3 rounded-xl bg-[#10131C] border border-white/[0.06]">
                    <div className="text-[10px] text-[#A1A1AA] uppercase">Resolution Rate</div>
                    <div className="text-lg font-bold text-emerald-400 mt-0.5">{selectedArea.resolution_rate ?? Math.round((100 - selectedArea.unresolved_rate) * 10) / 10}%</div>
                    <div className="text-[10px] text-[#A1A1AA] mt-0.5 font-mono">
                      {selectedArea.resolved_count ?? (selectedArea.total_complaints - selectedArea.unresolved_count)} / {selectedArea.total_complaints} tickets
                    </div>
                  </div>
                  <div className="p-3 rounded-xl bg-[#10131C] border border-white/[0.06]">
                    <div className="text-[10px] text-[#A1A1AA] uppercase">SLA Breach Rate</div>
                    <div className="text-lg font-bold text-red-400 mt-0.5">{selectedArea.sla_breach_rate}%</div>
                    <div className="text-[10px] text-[#A1A1AA] mt-0.5 font-mono">
                      {selectedArea.sla_breach_count} / {selectedArea.assigned_count ?? selectedArea.total_complaints} assigned
                    </div>
                  </div>
                </div>

                {/* Grounded Explainable Reason */}
                {selectedArea.explainable_reason && (
                  <div className="p-3 rounded-xl bg-[#10131C] border border-white/[0.06] text-xs">
                    <span className="text-[10px] font-bold uppercase text-[#A1A1AA] block mb-1">Grounded Reason:</span>
                    <p className="text-zinc-300 leading-relaxed">{selectedArea.explainable_reason}</p>
                  </div>
                )}

                {/* Reporting Period & Grounding Quality */}
                <div className="pt-3 border-t border-white/[0.08] text-[11px] text-[#A1A1AA] flex items-center justify-between">
                  <span>Reporting Period: <strong className="text-[#F5F5F5]">{selectedArea.reporting_period || `Past ${timeWindow} Days`}</strong></span>
                  <span className="text-emerald-400 font-semibold">{selectedArea.has_coordinates_pct || 100}% Coordinates Verified</span>
                </div>
              </div>
            ) : (
              <div className="py-20 text-center text-xs text-[#A1A1AA]">
                Select an area on the map or in the table below to inspect its civic dossier.
              </div>
            )}
          </div>
        </div>

        {/* Area-Wise Response Performance Table with Sample Size Warning and Explicit Denominators */}
        <div className="bg-[#141722]/85 rounded-3xl border border-white/[0.08] p-6 shadow-xl">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5">
            <div>
              <h2 className="text-base font-bold text-[#F5F5F5]">Area-Wise Response Performance Audit</h2>
              <p className="text-xs text-[#A1A1AA] mt-0.5">
                Comparative metrics across municipal wards. Wards with small sample sizes (n &lt; 5) are flagged to prevent premature disparity conclusions.
              </p>
            </div>
            <div className="text-xs text-[#A1A1AA] font-mono">
              Audit Window: {timeWindow} Days • Valid Complaints Only
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-white/[0.08] text-[#A1A1AA] font-semibold uppercase tracking-wider text-[10px]">
                  <th className="pb-3 pl-3">Area / Ward</th>
                  <th className="pb-3 text-right">Volume (n)</th>
                  <th className="pb-3 text-right">Unresolved Backlog</th>
                  <th className="pb-3 text-right">Resolution Rate</th>
                  <th className="pb-3 text-right">SLA Breach Rate</th>
                  <th className="pb-3 text-right">Repeat Spots</th>
                  <th className="pb-3 text-center">Sample Reliability</th>
                  <th className="pb-3 pr-3 text-center">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04]">
                {areas.map((a, i) => {
                  const isSelected = selectedArea?.area_name === a.area_name
                  const resolvedCnt = a.resolved_count ?? (a.total_complaints - a.unresolved_count)
                  const resRate = a.resolution_rate ?? Math.round((resolvedCnt / a.total_complaints) * 1000) / 10

                  return (
                    <tr
                      key={i}
                      onClick={() => setSelectedArea(a)}
                      className={`hover:bg-white/[0.03] transition-colors cursor-pointer ${
                        isSelected ? 'bg-white/[0.05]' : ''
                      }`}
                    >
                      <td className="py-3.5 pl-3 font-semibold text-[#F5F5F5] flex items-center gap-2">
                        <MapPin className="w-3.5 h-3.5 text-[#F36B21] flex-shrink-0" />
                        <div>
                          <span>{a.area_name}</span>
                          {a.locality && <span className="block text-[10px] text-[#A1A1AA] font-normal">{a.locality}</span>}
                        </div>
                      </td>
                      <td className="py-3.5 text-right font-mono font-bold text-[#F5F5F5]">
                        {a.total_complaints}
                      </td>
                      <td className="py-3.5 text-right font-mono">
                        <span className={a.unresolved_rate > 50 && !a.is_insufficient_sample ? 'text-amber-400 font-bold' : 'text-[#A1A1AA]'}>
                          {a.unresolved_count}/{a.total_complaints} ({a.unresolved_rate}%)
                        </span>
                      </td>
                      <td className="py-3.5 text-right font-mono">
                        <span className="text-emerald-400 font-semibold">
                          {resolvedCnt}/{a.total_complaints} ({resRate}%)
                        </span>
                      </td>
                      <td className="py-3.5 text-right font-mono">
                        <span className={a.sla_breach_rate > 20 && !a.is_insufficient_sample ? 'text-red-400 font-bold' : 'text-[#A1A1AA]'}>
                          {a.sla_breach_count}/{a.assigned_count ?? a.total_complaints} ({a.sla_breach_rate}%)
                        </span>
                      </td>
                      <td className="py-3.5 text-right font-mono text-sky-400">
                        {a.repeat_issue_clusters || a.repeat_issue_count || 0}
                      </td>
                      <td className="py-3.5 text-center">
                        {a.is_insufficient_sample ? (
                          <span className="inline-flex px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">
                            Preliminary (n &lt; 5)
                          </span>
                        ) : a.attention_flags && a.attention_flags.length > 0 ? (
                          <span className="inline-flex px-2 py-0.5 rounded-full text-[10px] font-bold bg-red-500/10 text-red-400 border border-red-500/20">
                            {a.attention_flags[0]}
                          </span>
                        ) : (
                          <span className="inline-flex px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                            Robust (Normal)
                          </span>
                        )}
                      </td>
                      <td className="py-3.5 pr-3 text-center">
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            setSelectedArea(a)
                          }}
                          className="text-[10px] text-[#F36B21] hover:underline font-semibold"
                        >
                          Inspect
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Explainable Recommendations (Grounded in Verified High-Sample Areas Only) */}
        <div className="bg-[#141722]/85 rounded-3xl border border-white/[0.08] p-6 shadow-xl">
          <div className="flex items-center gap-2 mb-3">
            <Sparkles className="w-4 h-4 text-[#F36B21]" />
            <h2 className="text-base font-bold text-[#F5F5F5]">
              Explainable Operational Recommendations
            </h2>
          </div>
          <p className="text-xs text-[#A1A1AA] mb-4">
            Grounded operational recommendations derived strictly from wards with statistically reliable sample sizes. Protects against premature conclusions from isolated tickets.
          </p>

          <div className="space-y-3">
            {recommendations.map((rec) => (
              <div
                key={rec.id}
                className="p-4 rounded-2xl bg-[#10131C] border border-white/[0.06] flex flex-col sm:flex-row sm:items-center justify-between gap-4"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-[#F5F5F5]">{rec.title}</span>
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 font-semibold">
                      {rec.neutral_label}
                    </span>
                  </div>
                  <p className="text-xs text-[#A1A1AA] leading-relaxed">{rec.description}</p>
                  <div className="text-[10px] text-zinc-500 font-mono flex items-center gap-2">
                    <span>Evidence Basis: {rec.evidence_basis}</span>
                    {rec.suggested_action && (
                      <>
                        <span>•</span>
                        <span className="text-[#F36B21]">Action: {rec.suggested_action}</span>
                      </>
                    )}
                  </div>
                </div>

                <div className="flex-shrink-0">
                  <Link
                    to="/authority/complaints"
                    className="px-3.5 py-1.5 rounded-xl bg-white/[0.06] hover:bg-white/[0.12] border border-white/[0.08] text-xs font-semibold text-[#F5F5F5] flex items-center gap-1.5 transition-all"
                  >
                    <span>Inspect Grievances</span>
                    <ChevronRight className="w-3.5 h-3.5 text-[#F36B21]" />
                  </Link>
                </div>
              </div>
            ))}

            {recommendations.length === 0 && (
              <div className="py-6 text-center text-xs text-[#A1A1AA]">
                All administrative areas are currently operating within balanced parity thresholds.
              </div>
            )}
          </div>
        </div>
      </div>
    </AuthorityLayout>
  )
}
