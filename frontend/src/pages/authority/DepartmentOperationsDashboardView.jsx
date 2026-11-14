import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  Wrench, Droplets, CloudRain, Trash2, Zap, Trees,
  AlertTriangle, CheckCircle2, Clock, MapPin, Flame,
  RefreshCw, Eye, ArrowRight, ChevronRight, FileText,
  UploadCloud, CheckCircle, Navigation, Shield, Layers,
  Send, RotateCcw, AlertCircle
} from 'lucide-react'
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { formatToIST, formatISTDateOnly } from '../../utils/dateTime'
import { resolveDepartment } from '../../utils/departmentContext'

const deptMarkerIcon = new L.Icon({
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
})

function MapAutoBounds({ markers }) {
  const map = useMap()
  useEffect(() => {
    if (!markers || markers.length === 0) return
    if (markers.length === 1) {
      map.setView([markers[0].latitude, markers[0].longitude], 13)
    } else {
      const bounds = L.latLngBounds(markers.map((m) => [m.latitude, m.longitude]))
      map.fitBounds(bounds, { padding: [35, 35], maxZoom: 14 })
    }
  }, [markers, map])
  return null
}

const DEPT_METAS = {
  RPW: {
    name: 'Roads & Public Works',
    title: 'Roads & Infrastructure Operations',
    code: 'RPW',
    icon: Wrench,
    accentColor: '#F36B21',
    heroImage: '/assets/dept_rpw.jpg',
    description: 'Pothole patchworks, roadway surface inspection, curb repairs & structural maintenance.'
  },
  WSS: {
    name: 'Water Supply & Sewerage',
    title: 'Water Supply & Sewerage Operations',
    code: 'WSS',
    icon: Droplets,
    accentColor: '#0284C7',
    heroImage: '/assets/dept_wss.jpg',
    description: 'Pipeline leak repair, potable distribution pressure, valve maintenance & sewer unclogging.'
  },
  WSD: {
    name: 'Water Supply & Sewerage',
    title: 'Water Supply & Sewerage Operations',
    code: 'WSD',
    icon: Droplets,
    accentColor: '#0284C7',
    heroImage: '/assets/dept_wss.jpg',
    description: 'Pipeline leak repair, potable distribution pressure, valve maintenance & sewer unclogging.'
  },
  DRN: {
    name: 'Storm Water Drainage',
    title: 'Storm Water & Drainage Operations',
    code: 'DRN',
    icon: CloudRain,
    accentColor: '#0D9488',
    heroImage: '/assets/dept_drn.jpg',
    description: 'Stormwater canal desilting, culvert clearing, flood mitigation & drain grates.'
  },
  SWM: {
    name: 'Sanitation & Waste Management',
    title: 'Sanitation & Waste Management Operations',
    code: 'SWM',
    icon: Trash2,
    accentColor: '#16A34A',
    heroImage: '/assets/dept_swm.jpg',
    description: 'Waste segregation collection, community bin clearance, street sanitation & landfill transit.'
  },
  ESM: {
    name: 'Electrical & Street Lighting',
    title: 'Electrical & Street Lighting Operations',
    code: 'ESM',
    icon: Zap,
    accentColor: '#D97706',
    heroImage: '/assets/dept_esm.jpg',
    description: 'LED street illumination, feeder box inspection, pole safety & transformer junction clearance.'
  },
  PID: {
    name: 'Public Infrastructure & Parks',
    title: 'Public Infrastructure & Parks Operations',
    code: 'PID',
    icon: Trees,
    accentColor: '#7C3AED',
    heroImage: '/assets/dept_pid.jpg',
    description: 'Public amenity repairs, park pathways, civic bench maintenance & recreational facility safety.'
  }
}

export default function DepartmentOperationsDashboardView({
  departmentCode = 'WSS',
  data,
  loading,
  onRefresh,
  complaints = [],
  onUpdateStatus,
  onAddNote
}) {
  const resolvedDept = resolveDepartment(departmentCode)
  const normCode = resolvedDept.code === 'WSD' ? 'WSS' : resolvedDept.code
  const meta = DEPT_METAS[normCode] || DEPT_METAS[resolvedDept.code] || DEPT_METAS.WSS
  const Icon = meta.icon

  const [activeModal, setActiveModal] = useState(null)
  const [selectedComplaintId, setSelectedComplaintId] = useState(null)
  const [fieldStatus, setFieldStatus] = useState('In Progress')
  const [fieldNotes, setFieldNotes] = useState('')
  const [actionLoading, setActionLoading] = useState(false)
  const [activeTab, setActiveTab] = useState('work') // 'work' | 'map' | 'sla'

  const assignedCount = complaints.length
  const pendingInspectionCount = complaints.filter((c) => (c.admin_status || c.status) === 'Assigned' || (c.admin_status || c.status) === 'Received' || (c.admin_status || c.status) === 'Pending Inspection').length
  const inProgressCount = complaints.filter((c) => (c.admin_status || c.status) === 'In Progress').length
  const resolutionSubmittedCount = complaints.filter((c) => (c.admin_status || c.status) === 'Resolution Submitted').length
  const overdueCount = complaints.filter((c) => (c.escalation_level || 0) > 0 || c.admin_status === 'Escalated').length

  const mappedIssues = complaints.filter((c) => c.latitude && c.longitude)
  const defaultCenter = mappedIssues.length > 0
    ? [mappedIssues[0].latitude, mappedIssues[0].longitude]
    : [17.0005, 81.804]

  const handleOpenActionModal = (id, currentStatus) => {
    setSelectedComplaintId(id)
    setFieldStatus(currentStatus === 'Assigned' ? 'In Progress' : (currentStatus || 'In Progress'))
    setFieldNotes('')
    setActiveModal('update_work')
  }

  const handleSubmitUpdate = async (e) => {
    e.preventDefault()
    if (!selectedComplaintId) return
    setActionLoading(true)
    try {
      if (onUpdateStatus) {
        await onUpdateStatus(selectedComplaintId, fieldStatus, fieldNotes)
      }
      setActiveModal(null)
    } catch (err) {
      alert(err.message || 'Failed to update work progress.')
    } finally {
      setActionLoading(false)
    }
  }

  return (
    <div className="space-y-8 max-w-7xl mx-auto font-sans">
      {/* 1. Hero Section (COSMO Warm Minimal Aesthetic) */}
      <div className="relative rounded-3xl bg-[#141722]/85 border border-white/[0.08] shadow-[0_4px_24px_rgba(24,24,27,0.04)] overflow-hidden">
        <div className="absolute top-0 right-1/4 w-96 h-96 bg-gradient-to-b from-[#FAF0E4]/60 to-transparent rounded-full blur-[100px] pointer-events-none" />

        <div className="grid grid-cols-1 lg:grid-cols-12 items-center min-h-[320px] relative z-10">
          <div className="lg:col-span-7 p-6 sm:p-10 flex flex-col justify-between">
            <div>
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#10131C] border border-white/[0.08] text-[11px] font-semibold text-[#A1A1AA] mb-4 shadow-xs">
                <span className="w-2 h-2 rounded-full animate-pulse" style={{ backgroundColor: meta.accentColor }} />
                <span className="uppercase tracking-wider">{meta.name} • DIVISION {meta.code}</span>
              </div>

              <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-[#F5F5F5] leading-tight">
                {meta.title}
              </h1>

              <p className="text-sm text-[#A1A1AA] mt-2.5 max-w-lg leading-relaxed">
                {meta.description}
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3 mt-6 pt-6 border-t border-white/[0.08]">
              <Link
                to="/authority/inspection-queue"
                className="px-5 py-2.5 rounded-xl bg-[#F36B21] hover:bg-[#E05A10] text-white font-semibold text-xs flex items-center gap-2 shadow-sm transition-all"
              >
                <Icon className="w-3.5 h-3.5" style={{ color: meta.accentColor }} />
                <span>Inspection Queue ({pendingInspectionCount})</span>
                <ChevronRight className="w-4 h-4" />
              </Link>
              <Link
                to="/authority/select-department"
                className="px-4 py-2.5 rounded-xl bg-[#141722]/85 hover:bg-white/[0.03] border border-white/[0.08] text-[#F5F5F5] font-semibold text-xs flex items-center gap-2 shadow-xs transition-all"
              >
                <Layers className="w-3.5 h-3.5 text-[#0284C7]" />
                <span>Switch Division Desk</span>
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

          <div className="lg:col-span-5 h-72 lg:h-full relative overflow-hidden flex items-end justify-center lg:justify-end">
            <div className="relative w-full h-full min-h-[300px]">
              <img
                src={meta.heroImage}
                alt={meta.name}
                className="w-full h-full object-cover object-center"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-[#141722] via-transparent to-transparent lg:bg-gradient-to-r lg:from-[#141722] lg:via-transparent lg:to-transparent" />
            </div>
          </div>
        </div>
      </div>

      {/* 2. Primary 5 KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <div className="p-5 rounded-2xl bg-[#141722]/85 border border-white/[0.08] shadow-xs">
          <div className="flex items-center justify-between text-zinc-500 mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-zinc-300">Assigned Tasks</span>
            <FileText className="w-4 h-4 text-zinc-500" />
          </div>
          <div className="text-3xl font-extrabold text-[#F5F5F5] tracking-tight">{assignedCount}</div>
          <div className="text-[11px] text-[#A1A1AA] mt-1 font-medium">{meta.code} Division work orders</div>
        </div>

        <div className="p-5 rounded-2xl bg-[#141722]/85 border border-white/[0.08] shadow-xs">
          <div className="flex items-center justify-between text-zinc-500 mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-amber-400">Pending Inspection</span>
            <Clock className="w-4 h-4 text-amber-500" />
          </div>
          <div className="text-3xl font-extrabold text-[#F5F5F5] tracking-tight">{pendingInspectionCount}</div>
          <div className="text-[11px] text-[#A1A1AA] mt-1 font-medium">Field inspection required</div>
        </div>

        <div className="p-5 rounded-2xl bg-[#141722]/85 border border-white/[0.08] shadow-xs">
          <div className="flex items-center justify-between text-zinc-500 mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-sky-400">In Progress</span>
            <Wrench className="w-4 h-4 text-sky-500" />
          </div>
          <div className="text-3xl font-extrabold text-[#F5F5F5] tracking-tight">{inProgressCount}</div>
          <div className="text-[11px] text-[#A1A1AA] mt-1 font-medium">Under active execution</div>
        </div>

        <div className="p-5 rounded-2xl bg-[#141722]/85 border border-white/[0.08] shadow-xs">
          <div className="flex items-center justify-between text-zinc-500 mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-purple-400">Resolution Submitted</span>
            <CheckCircle2 className="w-4 h-4 text-purple-500" />
          </div>
          <div className="text-3xl font-extrabold text-[#F5F5F5] tracking-tight">{resolutionSubmittedCount}</div>
          <div className="text-[11px] text-[#A1A1AA] mt-1 font-medium">Awaiting Officer closure</div>
        </div>

        <div className="p-5 rounded-2xl bg-[#141722]/85 border border-white/[0.08] shadow-xs col-span-2 lg:col-span-1">
          <div className="flex items-center justify-between text-zinc-500 mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-red-400">Overdue Tasks</span>
            <Flame className="w-4 h-4 text-red-500" />
          </div>
          <div className="text-3xl font-extrabold text-[#DC2626] tracking-tight">{overdueCount}</div>
          <div className="text-[11px] text-[#A1A1AA] mt-1 font-medium">Exceeding SLA target</div>
        </div>
      </div>

      {/* 3. Operational Tabs (Pill Controls) */}
      <div className="flex items-center justify-between flex-wrap gap-3 pb-2 border-b border-white/[0.08]">
        <div className="inline-flex p-1 rounded-full bg-[#10131C] border border-white/[0.08]">
          <button
            onClick={() => setActiveTab('work')}
            className={`px-4 py-1.5 rounded-full text-xs font-semibold transition-all cursor-pointer ${
              activeTab === 'work' ? 'bg-[#F36B21] text-white shadow-xs' : 'text-[#A1A1AA] hover:text-[#F5F5F5]'
            }`}
          >
            My Assigned Work ({assignedCount})
          </button>
          <button
            onClick={() => setActiveTab('map')}
            className={`px-4 py-1.5 rounded-full text-xs font-semibold transition-all cursor-pointer ${
              activeTab === 'map' ? 'bg-[#F36B21] text-white shadow-xs' : 'text-[#A1A1AA] hover:text-[#F5F5F5]'
            }`}
          >
            Geocoded Incident Map ({mappedIssues.length})
          </button>
          <button
            onClick={() => setActiveTab('sla')}
            className={`px-4 py-1.5 rounded-full text-xs font-semibold transition-all cursor-pointer ${
              activeTab === 'sla' ? 'bg-[#F36B21] text-white shadow-xs' : 'text-[#A1A1AA] hover:text-[#F5F5F5]'
            }`}
          >
            {meta.code} Division SLA & Activity
          </button>
        </div>
      </div>

      {/* Tab 1: Assigned Work Orders Table */}
      {activeTab === 'work' && (
        <div className="bg-[#141722]/85 rounded-3xl border border-white/[0.08] shadow-xs overflow-hidden">
          <div className="p-6 border-b border-white/[0.08] flex items-center justify-between flex-wrap gap-4">
            <div>
              <h2 className="text-base font-bold text-[#F5F5F5]">{meta.name} Work Orders</h2>
              <p className="text-xs text-[#A1A1AA] mt-0.5">
                Physical inspection, progress notes, and repair completion submission.
              </p>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-[#10131C] border-b border-white/[0.08] text-[#A1A1AA] font-bold uppercase tracking-wider text-[10px]">
                  <th className="py-3.5 px-5">ID & Category</th>
                  <th className="py-3.5 px-5">Description</th>
                  <th className="py-3.5 px-5">Location Coordinates</th>
                  <th className="py-3.5 px-5">Work Status</th>
                  <th className="py-3.5 px-5 text-right">Field Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.08]">
                {complaints.map((c) => (
                  <tr key={c.id} className="hover:bg-[#10131C]/60 transition-colors">
                    <td className="py-3.5 px-5">
                      <Link
                        to={`/authority/work-orders/${c.complaint_id}?dept=${resolvedDept.id}`}
                        className="font-bold text-[#F5F5F5] hover:text-[#F36B21] transition-colors"
                      >
                        {c.complaint_id}
                      </Link>
                      <div className="text-[11px] font-semibold text-[#A1A1AA] mt-0.5">{c.category}</div>
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
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full font-bold text-[10px] bg-white/[0.05] text-[#F5F5F5] border border-white/[0.08]">
                        <span>{c.admin_status || 'Assigned'}</span>
                      </span>
                    </td>

                    <td className="py-3.5 px-5 text-right whitespace-nowrap">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => handleOpenActionModal(c.complaint_id, c.admin_status)}
                          className="px-3 py-1 rounded-lg bg-[#F36B21] hover:bg-[#E05A10] text-white font-semibold text-[11px] transition-colors cursor-pointer"
                        >
                          Update Progress
                        </button>
                        <Link
                          to={`/authority/work-orders/${c.complaint_id}?dept=${resolvedDept.id}`}
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

      {/* Tab 2: Leaflet Map */}
      {activeTab === 'map' && (
        <div className="bg-[#141722]/85 rounded-3xl border border-white/[0.08] p-6 shadow-xs space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-bold text-[#F5F5F5] flex items-center gap-2">
                <MapPin className="w-4 h-4 text-[#F36B21]" />
                <span>{meta.code} Infrastructure Incident Map</span>
              </h2>
              <p className="text-xs text-[#A1A1AA] mt-0.5">
                Geolocated complaint coordinates on OpenStreetMap.
              </p>
            </div>
          </div>

          <div className="h-96 rounded-2xl overflow-hidden border border-white/[0.08] relative">
            <MapContainer center={defaultCenter} zoom={12} scrollWheelZoom={false} className="h-full w-full">
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              <MapAutoBounds markers={mappedIssues} />
              {mappedIssues.map((m) => (
                <Marker key={m.id} position={[m.latitude, m.longitude]} icon={deptMarkerIcon}>
                  <Popup>
                    <div className="text-xs p-1">
                      <strong>{m.complaint_id}</strong>
                      <div>{m.category}</div>
                      <div className="text-[#A1A1AA] text-[10px] mt-1">({m.latitude.toFixed(4)}, {m.longitude.toFixed(4)})</div>
                    </div>
                  </Popup>
                </Marker>
              ))}
            </MapContainer>
          </div>
        </div>
      )}

      {/* Tab 3: SLA & Activity */}
      {activeTab === 'sla' && (
        <div className="bg-[#141722]/85 rounded-3xl border border-white/[0.08] p-7 shadow-xs space-y-4">
          <h2 className="text-base font-bold text-[#F5F5F5]">{meta.name} SLA Performance</h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
            <div className="p-4 rounded-2xl bg-[#10131C] border border-white/[0.08]">
              <div className="font-semibold text-[#A1A1AA] uppercase">Division SLA Target</div>
              <div className="text-2xl font-extrabold text-[#F5F5F5] mt-1">
                {normCode === 'SWM' || normCode === 'ESM' ? '3 Days' : normCode === 'DRN' ? '4 Days' : normCode === 'WSS' ? '5 Days' : '7 Days'}
              </div>
              <div className="text-[#A1A1AA] mt-0.5">Mandated resolution timeline</div>
            </div>
            <div className="p-4 rounded-2xl bg-[#10131C] border border-white/[0.08]">
              <div className="font-semibold text-[#A1A1AA] uppercase">SLA Compliance Rate</div>
              <div className="text-2xl font-extrabold text-emerald-400 mt-1">100.0%</div>
              <div className="text-[#A1A1AA] mt-0.5">Complaints within SLA window</div>
            </div>
            <div className="p-4 rounded-2xl bg-[#10131C] border border-white/[0.08]">
              <div className="font-semibold text-[#A1A1AA] uppercase">Division Scoping</div>
              <div className="text-2xl font-extrabold text-[#F5F5F5] mt-1">Strict {meta.code}</div>
              <div className="text-[#A1A1AA] mt-0.5">Scoper bound to {meta.name}</div>
            </div>
          </div>
        </div>
      )}

      {/* MODAL: Update Work Progress */}
      {activeModal === 'update_work' && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#141722]/85 rounded-3xl p-6 sm:p-7 max-w-md w-full border border-white/[0.08] shadow-2xl space-y-4">
            <div>
              <h3 className="text-base font-bold text-[#F5F5F5]">Update Work Progress</h3>
              <p className="text-xs text-[#A1A1AA] mt-1">
                Complaint: <strong className="text-[#F5F5F5]">{selectedComplaintId}</strong>
              </p>
            </div>

            <form onSubmit={handleSubmitUpdate} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-zinc-300 mb-1">
                  Progress Status
                </label>
                <select
                  value={fieldStatus}
                  onChange={(e) => setFieldStatus(e.target.value)}
                  className="w-full p-2.5 rounded-xl bg-[#10131C] border border-white/[0.08] text-xs text-[#F5F5F5] font-semibold"
                >
                  <option value="Under Inspection">Under Inspection (Field crew deployed)</option>
                  <option value="In Progress">In Progress (Physical repair work underway)</option>
                  <option value="Resolution Submitted">Resolution Submitted (Repair complete, ready for Officer)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-300 mb-1">
                  Field Notes & Observations
                </label>
                <textarea
                  rows={3}
                  value={fieldNotes}
                  onChange={(e) => setFieldNotes(e.target.value)}
                  placeholder="e.g. Cleared pipeline obstruction, replaced joint gasket, and restored water supply."
                  className="w-full p-3 rounded-xl bg-[#10131C] border border-white/[0.08] text-xs text-[#F5F5F5]"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setActiveModal(null)}
                  className="px-4 py-2 rounded-xl text-[#A1A1AA] text-xs font-semibold hover:bg-white/[0.05] cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-5 py-2 rounded-xl bg-[#F36B21] hover:bg-[#E05A10] text-white text-xs font-semibold shadow-xs cursor-pointer"
                >
                  Save Progress
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
