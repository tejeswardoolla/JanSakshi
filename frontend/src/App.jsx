import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import ErrorBoundary from './components/ErrorBoundary'
import HomePage from './pages/HomePage'
import ReportPage from './pages/ReportPage'
import TrackPage from './pages/TrackPage'
import DuplicateReviewPage from './pages/DuplicateReviewPage'
import EmailManagementPage from './pages/EmailManagementPage'
import AuthorityLoginPage from './pages/AuthorityLoginPage'
import DepartmentSelectionPage from './pages/DepartmentSelectionPage'
import AuthorityDashboardPage from './pages/AuthorityDashboardPage'
import AuthorityComplaintsPage from './pages/AuthorityComplaintsPage'
import AuthorityComplaintDetailPage from './pages/AuthorityComplaintDetailPage'
import DepartmentWorkOrderDetailPage from './pages/authority/DepartmentWorkOrderDetailPage'
import AuthorityVerificationQueuePage from './pages/AuthorityVerificationQueuePage'
import RoadInspectionQueuePage from './pages/RoadInspectionQueuePage'
import AuthorityDepartmentsPage from './pages/AuthorityDepartmentsPage'
import AuthorityEscalationsPage from './pages/AuthorityEscalationsPage'
import AuthorityAuditPage from './pages/AuthorityAuditPage'
import AuthorityEquityIntelligencePage from './pages/authority/AuthorityEquityIntelligencePage'
import AuthorityResolutionReviewQueuePage from './pages/authority/AuthorityResolutionReviewQueuePage'
import AuthorityResolutionReviewDetailPage from './pages/authority/AuthorityResolutionReviewDetailPage'

export default function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            {/* Citizen & Public Grievance Portal */}
            <Route path="/" element={<HomePage />} />
            <Route path="/report" element={<ReportPage />} />
            <Route path="/track" element={<TrackPage />} />
            <Route path="/duplicates" element={<Navigate to="/authority/duplicates" replace />} />
            <Route path="/email-management" element={<Navigate to="/authority/email-management" replace />} />

            {/* Dedicated Authority & Department Portal */}
            <Route path="/login" element={<Navigate to="/authority/login" replace />} />
            <Route path="/authority/login" element={<AuthorityLoginPage />} />
            <Route path="/authority/select-department" element={<DepartmentSelectionPage />} />
            <Route path="/authority" element={<AuthorityDashboardPage />} />
            <Route path="/authority-dashboard" element={<Navigate to="/authority" replace />} />
            <Route path="/authority/complaints" element={<AuthorityComplaintsPage />} />
            <Route path="/authority/complaints/:id" element={<AuthorityComplaintDetailPage />} />
            <Route path="/authority/work-orders/:id" element={<DepartmentWorkOrderDetailPage />} />
            <Route path="/authority/verification-queue" element={<AuthorityVerificationQueuePage />} />
            <Route path="/authority/inspection-queue" element={<RoadInspectionQueuePage />} />
            <Route path="/authority/departments" element={<AuthorityDepartmentsPage />} />
            <Route path="/authority/escalations" element={<AuthorityEscalationsPage />} />
            <Route path="/authority/audit" element={<AuthorityAuditPage />} />
            <Route path="/authority/equity-intelligence" element={<Navigate to="/authority" replace />} />
            <Route path="/authority/resolution-review" element={<AuthorityResolutionReviewQueuePage />} />
            <Route path="/authority/resolution-review/:id" element={<AuthorityResolutionReviewDetailPage />} />
            <Route path="/authority/duplicates" element={<DuplicateReviewPage />} />
            <Route path="/authority/email-management" element={<EmailManagementPage />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ErrorBoundary>
  )
}
