import React, { useState, useEffect } from 'react'
import { useNavigate, useLocation, Link } from 'react-router-dom'
import { RefreshCw, AlertCircle, Shield, ArrowLeft, Layers } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import AuthorityLayout from '../components/AuthorityLayout'
import AdminDashboardView from './authority/AdminDashboardView'
import AuthorityOfficerDashboardView from './authority/AuthorityOfficerDashboardView'
import RoadsDepartmentDashboardView from './authority/RoadsDepartmentDashboardView'
import DepartmentOperationsDashboardView from './authority/DepartmentOperationsDashboardView'
import { resolveDepartment, saveDepartmentContext } from '../utils/departmentContext'

export default function AuthorityDashboardPage() {
  const { user, isAuthenticated, authFetch } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [data, setData] = useState(null)
  const [complaints, setComplaints] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [is403Forbidden, setIs403Forbidden] = useState(false)

  // Resolve active department cleanly for department officers
  const searchParams = new URLSearchParams(location.search)
  const queryDept = searchParams.get('dept')
  const storedDeptId = localStorage.getItem('jansakshi_active_dept_id')
  const storedDeptCode = localStorage.getItem('jansakshi_active_dept_code')
  
  const activeDept = resolveDepartment(queryDept || storedDeptId || storedDeptCode, user)

  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/authority/login')
      return
    }

    if (user?.role === 'department_officer') {
      // Check multi-department vs single department routing
      const authorizedIds = user?.authorized_departments || (user?.department_id ? [user.department_id] : [])
      const hasAll = user?.has_all_departments || false
      
      // If direct access with no selection in storage and no query param, check if needs selection
      if (!storedDeptId && !queryDept && (hasAll || authorizedIds.length > 1)) {
        navigate('/authority/select-department')
        return
      }

      // Persist normalized active department
      saveDepartmentContext(activeDept)
    }

    fetchDashboardData()
  }, [isAuthenticated, navigate, location.search, user])

  const fetchDashboardData = async () => {
    setLoading(true)
    setError(null)
    setIs403Forbidden(false)
    try {
      let overviewUrl = '/api/authority/overview'
      let complaintsUrl = '/api/authority/complaints?limit=50'

      if (user?.role === 'department_officer') {
        const deptId = activeDept?.id || 1
        overviewUrl += `?department_id=${deptId}`
        complaintsUrl += `&department_id=${deptId}`
      }

      const [overRes, compRes] = await Promise.all([
        authFetch(overviewUrl),
        authFetch(complaintsUrl)
      ])

      if (overRes.status === 403 || compRes.status === 403) {
        setIs403Forbidden(true)
        throw new Error(`Access forbidden: You do not have authorization for ${activeDept.name}.`)
      }

      if (!overRes.ok) throw new Error('Failed to load municipal overview metrics.')
      const overJson = await overRes.json()
      setData(overJson)

      if (compRes.ok) {
        const compJson = await compRes.json()
        setComplaints(compJson.items || [])
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  // --- Actions Handlers ---
  const handleVerify = async (complaintId, notes) => {
    const res = await authFetch(`/api/authority/complaints/${complaintId}/verify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ notes })
    })
    if (!res.ok) throw new Error('Failed to verify complaint.')
    fetchDashboardData()
  }

  const handleReject = async (complaintId, reason) => {
    const res = await authFetch(`/api/authority/complaints/${complaintId}/reject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason })
    })
    if (!res.ok) throw new Error('Failed to reject complaint.')
    fetchDashboardData()
  }

  const handleRequestInfo = async (complaintId, notes) => {
    const res = await authFetch(`/api/authority/complaints/${complaintId}/request-info`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ notes })
    })
    if (!res.ok) throw new Error('Failed to request additional info.')
    fetchDashboardData()
  }

  const handleAssign = async (complaintId, departmentId) => {
    const res = await authFetch(`/api/authority/complaints/${complaintId}/assign`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ department_id: departmentId })
    })
    if (!res.ok) throw new Error('Failed to assign department.')
    fetchDashboardData()
  }

  const handleUpdateStatus = async (complaintId, status, notes) => {
    const res = await authFetch(`/api/authority/complaints/${complaintId}/status`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status, notes })
    })
    if (!res.ok) throw new Error('Failed to update status.')
    fetchDashboardData()
  }

  const handleAddNote = async (complaintId, notes) => {
    const res = await authFetch(`/api/authority/complaints/${complaintId}/notes`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ notes })
    })
    if (!res.ok) throw new Error('Failed to add internal note.')
    fetchDashboardData()
  }

  const role = user?.role || 'authority_officer'

  const getPageTitle = () => {
    if (role === 'admin') return 'Complaint Management Centre'
    if (role === 'department_officer') {
      const code = (activeDept?.code || 'RPW').toUpperCase()
      if (code === 'RPW') return 'Roads & Infrastructure Operations'
      if (code === 'WSD' || code === 'WSS') return 'Water Supply & Sewerage Operations'
      if (code === 'DRN') return 'Storm Water & Drainage Operations'
      if (code === 'SWM') return 'Sanitation & Waste Management Operations'
      if (code === 'ESM') return 'Electrical & Street Lighting Operations'
      if (code === 'PID') return 'Public Infrastructure & Parks Operations'
      return `${code} Field Operations`
    }
    return 'Civic Decision & Dispatch Centre'
  }

  const pendingComplaints = complaints.filter((c) => c.verification_status === 'pending')

  if (loading && !data) {
    return (
      <AuthorityLayout pageTitle={getPageTitle()} breadcrumbs={['Operations Desk', 'Overview']}>
        <div className="py-24 text-center">
          <RefreshCw className="w-8 h-8 text-[#F36B21] animate-spin mx-auto mb-3" />
          <p className="text-xs text-stone-500 font-medium">Computing live municipal intelligence...</p>
        </div>
      </AuthorityLayout>
    )
  }

  if (is403Forbidden) {
    return (
      <AuthorityLayout pageTitle="Division Authorization Restricted" breadcrumbs={['Operations Desk', 'Access Denied']}>
        <div className="max-w-xl mx-auto px-6 py-20 text-center">
          <div className="w-16 h-16 rounded-2xl bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-amber-400 mx-auto mb-4">
            <Shield className="w-8 h-8" />
          </div>
          <h2 className="text-xl font-bold text-[#F5F5F5]">Division Authorization Restricted</h2>
          <p className="text-xs text-[#A1A1AA] mt-2 leading-relaxed">
            Your department credentials do not permit querying operational data for <span className="font-bold text-[#F5F5F5]">{activeDept?.name || 'this department'}</span>.
          </p>
          <div className="mt-6 flex items-center justify-center gap-3">
            <Link
              to="/authority/select-department"
              className="inline-flex items-center gap-2 px-4 py-2.5 bg-[#F36B21] hover:bg-[#E05A10] text-white rounded-xl text-xs font-semibold shadow-md transition-all"
            >
              <Layers className="w-4 h-4" />
              <span>Select Authorized Division</span>
            </Link>
          </div>
        </div>
      </AuthorityLayout>
    )
  }

  return (
    <AuthorityLayout pageTitle={getPageTitle()} breadcrumbs={['Operations Desk', activeDept?.name || 'Overview']}>
      {error && (
        <div className="mb-6 p-4 rounded-2xl bg-red-500/10 border border-red-500/30 text-red-400 text-xs flex items-center justify-between shadow-xs">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
          <button onClick={fetchDashboardData} className="underline hover:text-red-300 cursor-pointer font-semibold">
            Retry Sync
          </button>
        </div>
      )}

      {/* Dynamic Role-Specific Dashboard Rendering */}
      {role === 'admin' && (
        <AdminDashboardView
          data={{ ...data, complaints }}
          loading={loading}
          onRefresh={fetchDashboardData}
        />
      )}

      {role === 'department_officer' && (
        ((activeDept?.code || 'RPW') === 'RPW') ? (
          <RoadsDepartmentDashboardView
            data={{ ...data, complaints }}
            loading={loading}
            onRefresh={fetchDashboardData}
            complaints={complaints}
            onUpdateStatus={handleUpdateStatus}
            onAddNote={handleAddNote}
          />
        ) : (
          <DepartmentOperationsDashboardView
            departmentCode={activeDept?.code || 'RPW'}
            data={{ ...data, complaints }}
            loading={loading}
            onRefresh={fetchDashboardData}
            complaints={complaints}
            onUpdateStatus={handleUpdateStatus}
            onAddNote={handleAddNote}
          />
        )
      )}

      {role === 'authority_officer' && (
        <AuthorityOfficerDashboardView
          data={{ ...data, complaints }}
          loading={loading}
          onRefresh={fetchDashboardData}
          pendingComplaints={pendingComplaints}
          onVerify={handleVerify}
          onReject={handleReject}
          onRequestInfo={handleRequestInfo}
          onAssign={handleAssign}
        />
      )}
    </AuthorityLayout>
  )
}
