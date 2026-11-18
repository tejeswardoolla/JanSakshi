import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ArrowLeft,
  Mail,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  Clock,
  ExternalLink,
  ShieldCheck,
  Paperclip,
  RotateCcw,
  Send,
  HelpCircle,
  ChevronRight,
  Info,
  X,
  FileText
} from 'lucide-react'
import { useNavigate, useSearchParams, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import AuthorityLayout from '../components/AuthorityLayout'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import { formatToIST } from '../utils/dateTime'

export default function EmailManagementPage() {
  const { authFetch } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const isInternal = location.pathname.startsWith('/authority')
  const [searchParams] = useSearchParams()
  const connectedParam = searchParams.get('connected')
  const errorParam = searchParams.get('error')

  const [status, setStatus] = useState(null)
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [filter, setFilter] = useState('')
  const [actionNotice, setActionNotice] = useState(null)
  const [selectedMessage, setSelectedMessage] = useState(null)
  const [showSetupGuide, setShowSetupGuide] = useState(false)
  const [reviewingId, setReviewingId] = useState(null)

  const fetchStatusAndMessages = async () => {
    setLoading(true)
    try {
      const messagesUrl = `/api/email/messages?limit=200${filter ? `&status=${encodeURIComponent(filter)}` : ''}`
      const [statusRes, msgsRes] = await Promise.all([
        authFetch('/api/email/status'),
        authFetch(messagesUrl)
      ])

      if (statusRes.status === 401 || msgsRes.status === 401) {
        navigate('/authority/login?session_expired=true')
        return
      }

      if (statusRes.ok) {
        const sData = await statusRes.json()
        setStatus(sData)
      }
      if (msgsRes.ok) {
        const mData = await msgsRes.json()
        setMessages(Array.isArray(mData) ? mData : [])
      } else {
        const errData = await msgsRes.json().catch(() => ({}))
        setActionNotice({ type: 'error', text: errData.detail || 'Failed to load email messages.' })
      }
    } catch (err) {
      setActionNotice({ type: 'error', text: 'Failed to communicate with email backend service.' })
    } finally {
      setLoading(false)
    }
  }

  const handleConfirmCivic = async (messageId) => {
    setReviewingId(messageId)
    try {
      const res = await authFetch(`/api/email/messages/${messageId}/confirm-civic`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      })
      const data = await res.json()
      if (res.ok) {
        setActionNotice({
          type: 'success',
          text: `Promoted email #${messageId} to Complaint ${data.complaint_id}! Acknowledgement sent.`
        })
        setSelectedMessage(null)
        fetchStatusAndMessages()
      } else {
        setActionNotice({ type: 'error', text: data.detail || 'Failed to promote email to civic complaint.' })
      }
    } catch (err) {
      setActionNotice({ type: 'error', text: 'Network request to promote email failed.' })
    } finally {
      setReviewingId(null)
    }
  }

  const handleMarkNonCivic = async (messageId) => {
    setReviewingId(messageId)
    try {
      const res = await authFetch(`/api/email/messages/${messageId}/mark-non-civic`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: 'Admin manual non-civic classification' })
      })
      const data = await res.json()
      if (res.ok) {
        setActionNotice({
          type: 'success',
          text: `Email #${messageId} verified as non-civic and ignored.`
        })
        setSelectedMessage(null)
        fetchStatusAndMessages()
      } else {
        setActionNotice({ type: 'error', text: data.detail || 'Failed to mark email as non-civic.' })
      }
    } catch (err) {
      setActionNotice({ type: 'error', text: 'Network request to mark non-civic failed.' })
    } finally {
      setReviewingId(null)
    }
  }

  useEffect(() => {
    fetchStatusAndMessages()
    if (connectedParam) {
      setActionNotice({ type: 'success', text: 'Gmail OAuth successfully authorized and connected!' })
    } else if (errorParam) {
      setActionNotice({ type: 'error', text: `OAuth Error: ${errorParam}` })
    }
  }, [filter, connectedParam, errorParam])

  const handleSync = async () => {
    setSyncing(true)
    setActionNotice(null)
    try {
      const res = await authFetch('/api/email/sync', { method: 'POST' })
      if (res.status === 401) {
        navigate('/authority/login?session_expired=true')
        return
      }
      const data = await res.json()
      if (res.ok) {
        setActionNotice({
          type: 'success',
          text: data.status === 'success'
            ? `Sync complete: ${data.processed} complaint(s) created, ${data.ignored} ignored, ${data.skipped_previously_processed} already processed.`
            : (data.message || 'Sync completed.')
        })
        fetchStatusAndMessages()
      } else {
        setActionNotice({ type: 'error', text: data.detail || 'Inbox sync failed.' })
      }
    } catch (err) {
      setActionNotice({ type: 'error', text: 'Network request to sync inbox failed.' })
    } finally {
      setSyncing(false)
    }
  }

  const handleConnect = async () => {
    try {
      const res = await authFetch('/api/email/oauth/start', { method: 'POST' })
      const data = await res.json()
      if (res.ok && data.authorization_url) {
        window.location.href = data.authorization_url
      } else {
        setActionNotice({ type: 'error', text: data.detail || 'Unable to generate OAuth authorization URL.' })
        setShowSetupGuide(true)
      }
    } catch (err) {
      setActionNotice({ type: 'error', text: 'Failed to initiate OAuth flow.' })
    }
  }

  const handleDisconnect = async () => {
    if (!window.confirm('Disconnect Gmail account and clear local OAuth tokens?')) return
    try {
      const res = await authFetch('/api/email/disconnect', { method: 'POST' })
      if (res.ok) {
        setActionNotice({ type: 'success', text: 'Gmail disconnected. OAuth tokens removed.' })
        fetchStatusAndMessages()
      }
    } catch (err) {
      setActionNotice({ type: 'error', text: 'Failed to disconnect.' })
    }
  }

  const [reExtracting, setReExtracting] = useState(false)

  const handleRetry = async (msgId) => {
    try {
      const res = await authFetch(`/api/email/messages/${msgId}/retry`, { method: 'POST' })
      const data = await res.json()
      if (res.ok) {
        setActionNotice({ type: 'success', text: `Retried message: ${data.status} (Complaint: ${data.complaint_id || 'N/A'})` })
        fetchStatusAndMessages()
      } else {
        setActionNotice({ type: 'error', text: data.detail || 'Retry failed.' })
      }
    } catch (err) {
      setActionNotice({ type: 'error', text: 'Retry request failed.' })
    }
  }

  const handleReExtract = async (msgId) => {
    setReExtracting(true)
    try {
      const res = await authFetch(`/api/email/messages/${msgId}/re-extract`, { method: 'POST' })
      const data = await res.json()
      if (res.ok) {
        setSelectedMessage(data)
        fetchStatusAndMessages()
        setActionNotice({ type: 'success', text: 'Email extraction & complaint location updated in-place.' })
      } else {
        setActionNotice({ type: 'error', text: data.detail || 'Re-extraction failed.' })
      }
    } catch (err) {
      setActionNotice({ type: 'error', text: 'Re-extraction request failed.' })
    } finally {
      setReExtracting(false)
    }
  }

  const renderContent = () => (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 pb-6 border-b border-white/[0.08]">
        <div>
          <div className="inline-flex items-center gap-2 bg-[#F36B21]/15 border border-[#F36B21]/30 px-3 py-1 rounded-full mb-3">
            <Mail size={13} className="text-[#F36B21]" />
            <span className="text-[#F36B21] text-[11px] font-bold tracking-widest uppercase">
              Phase 6 Gmail AI Integration & Ingestion Desk
            </span>
          </div>
          <h1 className="text-3xl sm:text-4xl font-extrabold text-[#F5F5F5] tracking-tight">
            Email Grievance Management
          </h1>
          <p className="text-[#A1A1AA] text-sm mt-2 max-w-2xl leading-relaxed">
            Automated municipal email ingestion powered by Google Gmail API and Gemini AI. Processes citizen emails, extracts civic categories and landmarks, saves evidence attachments, and automatically replies with official tracking IDs.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowSetupGuide(!showSetupGuide)}
            className="flex items-center gap-1.5 bg-[#141722]/85 hover:bg-[#191D2A] border border-white/[0.08] text-[#F5F5F5] px-3.5 py-2.5 rounded-xl text-xs font-semibold transition-all cursor-pointer shadow-sm"
          >
            <HelpCircle size={14} />
            <span>OAuth Setup Guide</span>
          </button>
          <button
            onClick={handleSync}
            disabled={syncing || loading}
            className="flex items-center gap-2 bg-[#F36B21] hover:bg-[#E05A10] text-white px-4 py-2.5 rounded-xl text-xs font-semibold shadow-md shadow-[#F36B21]/20 transition-all disabled:opacity-50 cursor-pointer"
          >
            <RefreshCw size={14} className={syncing ? 'animate-spin' : ''} />
            <span>{syncing ? 'Syncing Inbox...' : 'Sync Inbox Now'}</span>
          </button>
        </div>
      </div>

        {/* Global Toast / Notification */}
        <AnimatePresence>
          {actionNotice && (
            <motion.div
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className={`p-4 rounded-2xl mb-8 text-sm flex items-center justify-between border ${
                actionNotice.type === 'success'
                  ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                  : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
              }`}
            >
              <div className="flex items-center gap-3">
                {actionNotice.type === 'success' ? (
                  <CheckCircle2 size={18} className="text-emerald-400 flex-shrink-0" />
                ) : (
                  <AlertCircle size={18} className="text-rose-400 flex-shrink-0" />
                )}
                <span>{actionNotice.text}</span>
              </div>
              <button
                onClick={() => setActionNotice(null)}
                className="text-xs hover:underline opacity-80"
              >
                Dismiss
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Setup Guide Collapsible */}
        <AnimatePresence>
          {showSetupGuide && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="overflow-hidden mb-8"
            >
              <div className="bg-[#121316] border border-white/10 rounded-2xl p-6 text-xs text-white/70 space-y-4">
                <div className="flex items-center justify-between border-b border-white/5 pb-3">
                  <h3 className="text-sm font-bold text-white flex items-center gap-2">
                    <ShieldCheck size={16} className="text-[#F36B21]" />
                    Official JanSakshi Gmail OAuth 2.0 Setup Guide
                  </h3>
                  <button onClick={() => setShowSetupGuide(false)} className="text-white/40 hover:text-white">
                    <X size={16} />
                  </button>
                </div>
                <div className="bg-[#F36B21]/10 border border-[#F36B21]/20 p-3 rounded-xl text-white/90">
                  <p><strong>Designated Municipal Inbox:</strong> <span className="font-mono text-[#F36B21] font-bold">jansakshiofficial@gmail.com</span></p>
                  <p className="text-[11px] text-white/60 mt-1">Please ensure you sign in with this exact Google account when authorizing the application.</p>
                </div>
                <ol className="list-decimal list-inside space-y-2 leading-relaxed">
                  <li>Visit the <a href="https://console.cloud.google.com" target="_blank" rel="noreferrer" className="text-[#F36B21] underline">Google Cloud Console</a> and create or select your project.</li>
                  <li>Enable the <strong>Gmail API</strong> under APIs & Services &rarr; Library.</li>
                  <li>Configure the <strong>OAuth Consent Screen</strong>:
                    <ul className="list-disc list-inside ml-4 mt-1 space-y-1 text-white/60">
                      <li>Select User Type (External or Internal).</li>
                      <li>Add scopes: <code className="bg-black/40 px-1 py-0.5 rounded text-[#F36B21]">https://www.googleapis.com/auth/gmail.readonly</code> and <code className="bg-black/40 px-1 py-0.5 rounded text-[#F36B21]">https://www.googleapis.com/auth/gmail.send</code></li>
                      <li>If app is in <em>Testing</em> mode, add <strong className="text-white font-mono">jansakshiofficial@gmail.com</strong> under <strong>Test Users</strong>.</li>
                    </ul>
                  </li>
                  <li>Create Credentials &rarr; <strong>OAuth 2.0 Client ID</strong> &rarr; Application type: <em>Web application</em>.</li>
                  <li>Add Authorized redirect URI: <code className="bg-black/40 px-1 py-0.5 rounded text-[#F36B21]">https://your-domain/api/email/oauth/callback</code> (or <code className="bg-black/40 px-1 py-0.5 rounded text-[#F36B21]">http://localhost:8000/api/email/oauth/callback</code> for local testing).</li>
                  <li>Add <code className="bg-black/40 px-1 py-0.5 rounded">GMAIL_CLIENT_ID</code> and <code className="bg-black/40 px-1 py-0.5 rounded">GMAIL_CLIENT_SECRET</code> to <code className="bg-black/40 px-1 py-0.5 rounded">backend/.env</code>.</li>
                  <li>Click <em>Connect Gmail Account</em> below and log in as <strong className="text-white font-mono">jansakshiofficial@gmail.com</strong>.</li>
                </ol>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Gmail Connection Status Card */}
        {status && (
          <div className="bg-[#121316] border border-white/10 rounded-3xl p-6 sm:p-8 mb-8 shadow-xl space-y-6">
            <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6 border-b border-white/10 pb-6">
              <div className="flex items-center gap-4">
                <div className={`w-12 h-12 rounded-2xl flex items-center justify-center ${
                  status.authenticated && status.mailbox_match
                    ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                    : status.status === 'account_mismatch'
                    ? 'bg-rose-500/15 text-rose-400 border border-rose-500/30'
                    : status.configured
                    ? 'bg-amber-500/15 text-amber-400 border border-amber-500/30'
                    : 'bg-white/5 text-white/40 border border-white/10'
                }`}>
                  <Mail size={24} />
                </div>
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="text-lg font-bold text-white">
                      {status.authenticated
                        ? (status.mailbox_match ? 'Official Gmail Inbox Connected' : 'Gmail Connected (Account Mismatch)')
                        : 'Official Gmail Inbox Standby'}
                    </h3>
                    <span className={`text-[10px] uppercase font-bold px-2.5 py-0.5 rounded-full ${
                      status.authenticated && status.mailbox_match
                        ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                        : status.status === 'account_mismatch'
                        ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
                        : status.configured
                        ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                        : 'bg-white/10 text-white/40'
                    }`}>
                      {status.status}
                    </span>
                  </div>

                  <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs mt-1.5">
                    <span className="text-white/70">
                      Official Mailbox: <strong className="text-[#F36B21] font-mono">{status.official_inbox_address || 'jansakshiofficial@gmail.com'}</strong>
                    </span>
                    <span className="text-white/40">|</span>
                    <span className="text-white/70">
                      Connected Account: <strong className="text-white font-mono">{status.connected_email || status.email_address || 'None (Awaiting Authorization)'}</strong>
                    </span>
                  </div>
                  <p className="text-white/40 text-[11px] mt-1">
                    {status.message}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                {status.authenticated ? (
                  <button
                    onClick={handleDisconnect}
                    className="text-xs text-rose-300 hover:text-rose-200 border border-rose-500/30 hover:bg-rose-500/10 px-4 py-2 rounded-xl transition-all font-semibold"
                  >
                    Disconnect Mailbox
                  </button>
                ) : (
                  <button
                    onClick={handleConnect}
                    className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-500 text-white px-5 py-2.5 rounded-xl text-xs font-semibold shadow-lg shadow-emerald-600/20 transition-all"
                  >
                    <ShieldCheck size={14} />
                    <span>Authorize jansakshiofficial@gmail.com</span>
                  </button>
                )}
              </div>
            </div>

            {/* Account Mismatch Warning Alert */}
            {status.authenticated && !status.mailbox_match && (
              <div className="bg-rose-500/10 border border-rose-500/30 rounded-2xl p-4 text-xs text-rose-200 flex items-start gap-3">
                <AlertTriangle size={18} className="text-rose-400 flex-shrink-0 mt-0.5" />
                <div>
                  <strong className="block text-rose-300 font-bold mb-0.5">
                    Gmail Account Mismatch Detected
                  </strong>
                  The authenticated account (<span className="font-mono text-white underline">{status.connected_email}</span>) does not match the configured official mailbox (<span className="font-mono text-white underline">{status.official_inbox_address}</span>). To prevent complaints from being routed to an unofficial inbox, please disconnect and authorize <strong className="text-white font-mono">jansakshiofficial@gmail.com</strong>.
                </div>
              </div>
            )}

            {/* Metrics Counters */}
            <div className="grid grid-cols-2 sm:grid-cols-6 gap-3 text-xs">
              <div className="bg-[#08090B] p-4 rounded-2xl border border-white/5">
                <span className="text-white/40 block text-[10px] uppercase tracking-wider">Total Received</span>
                <span className="text-xl font-bold text-white mt-1 block">{status.total_messages_received}</span>
              </div>
              <div className="bg-[#08090B] p-4 rounded-2xl border border-white/5">
                <span className="text-white/40 block text-[10px] uppercase tracking-wider">Complaints Registered</span>
                <span className="text-xl font-bold text-emerald-400 mt-1 block">{status.total_processed}</span>
              </div>
              <div className="bg-[#08090B] p-4 rounded-2xl border border-white/5">
                <span className="text-white/40 block text-[10px] uppercase tracking-wider">Needs Review</span>
                <span className={`text-xl font-bold mt-1 block ${status.total_needs_review > 0 ? 'text-[#F36B21]' : 'text-white/50'}`}>
                  {status.total_needs_review || 0}
                </span>
              </div>
              <div className="bg-[#08090B] p-4 rounded-2xl border border-white/5">
                <span className="text-white/40 block text-[10px] uppercase tracking-wider">Awaiting Location</span>
                <span className="text-xl font-bold text-amber-400 mt-1 block">{status.total_awaiting_info}</span>
              </div>
              <div className="bg-[#08090B] p-4 rounded-2xl border border-white/5">
                <span className="text-white/40 block text-[10px] uppercase tracking-wider">Non-Civic Ignored</span>
                <span className="text-xl font-bold text-white/50 mt-1 block">{status.total_ignored}</span>
              </div>
              <div className="bg-[#08090B] p-4 rounded-2xl border border-white/5">
                <span className="text-white/40 block text-[10px] uppercase tracking-wider">Failures</span>
                <span className="text-xl font-bold text-rose-400 mt-1 block">{status.total_failed}</span>
              </div>
            </div>
          </div>
        )}

        {/* Status Filter Tabs */}
        <div className="bg-[#121316] border border-white/10 rounded-2xl p-4 mb-6 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            {[
              { id: '', label: 'All Ingested', count: status?.total_messages_received },
              { id: 'needs_review', label: 'Needs Review', count: status?.total_needs_review },
              { id: 'processed', label: 'Processed (Complaints)', count: status?.total_processed },
              { id: 'awaiting_information', label: 'Awaiting Location', count: status?.total_awaiting_info },
              { id: 'ignored', label: 'Ignored (Non-Civic)', count: status?.total_ignored },
              { id: 'failed', label: 'Failed', count: status?.total_failed },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setFilter(tab.id)}
                className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all ${
                  filter === tab.id
                    ? 'bg-[#F36B21] text-white shadow-md shadow-[#F36B21]/20'
                    : 'bg-white/5 text-white/60 hover:text-white hover:bg-white/10'
                }`}
              >
                <span>{tab.label}</span>
                {typeof tab.count === 'number' && (
                  <span className={`text-[10px] px-1.5 py-0.2 rounded-full font-bold ${
                    filter === tab.id ? 'bg-white/20 text-white' : 'bg-white/10 text-white/50'
                  }`}>
                    {tab.count}
                  </span>
                )}
              </button>
            ))}
          </div>

          <span className="text-white/40 text-xs">
            Showing {messages.length} record(s)
          </span>
        </div>

        {/* Email Messages Table / List */}
        {loading ? (
          <div className="text-center py-24 space-y-3">
            <RefreshCw size={28} className="animate-spin text-[#F36B21] mx-auto" />
            <p className="text-white/50 text-sm">Loading email audit records...</p>
          </div>
        ) : messages.length === 0 ? (
          <div className="bg-[#121316] border border-white/5 rounded-3xl p-16 text-center space-y-3">
            <Mail size={36} className="text-white/20 mx-auto" />
            <h3 className="text-white font-bold text-lg">No Messages Found</h3>
            <p className="text-white/40 text-xs max-w-md mx-auto">
              No emails matching filter "{filter || 'all'}". When citizens send complaint emails to the connected mailbox, they will automatically appear here.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {messages.map((m) => {
              return (
                <div
                  key={m.id}
                  className="bg-[#121316] border border-white/10 hover:border-white/20 transition-all rounded-2xl p-5 space-y-3"
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-white/5 pb-3">
                    <div className="flex items-center gap-3">
                      <span className="font-mono text-xs text-white/40">#{m.id}</span>
                      <span className={`text-[10px] font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full ${
                        m.processing_status === 'processed'
                          ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                          : m.processing_status === 'awaiting_information'
                          ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                          : m.processing_status === 'needs_review'
                          ? 'bg-[#F36B21]/20 text-[#F36B21] border border-[#F36B21]/40 animate-pulse'
                          : m.processing_status === 'ignored'
                          ? 'bg-white/10 text-white/40'
                          : 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
                      }`}>
                        {m.processing_status === 'needs_review' ? 'Needs Admin Review' : m.processing_status}
                      </span>
                      {m.is_follow_up && (
                        <span className="bg-sky-500/20 text-sky-300 border border-sky-500/40 text-[10px] uppercase font-bold px-2 py-0.5 rounded-full">
                          Follow-up Reply
                        </span>
                      )}
                      {m.complaint_id && (
                        <button
                          onClick={() => navigate(`/track?id=${m.complaint_id}`)}
                          className="font-mono text-[#F36B21] hover:underline font-bold text-xs flex items-center gap-1"
                        >
                          <span>{m.complaint_id}</span>
                          <ExternalLink size={11} />
                        </button>
                      )}
                    </div>

                    <div className="flex items-center gap-4 text-xs text-white/40">
                      {m.has_attachments && (
                        <span className="flex items-center gap-1 text-white/70">
                          <Paperclip size={12} className="text-[#F36B21]" />
                          <span>{m.attachments_count} file(s)</span>
                        </span>
                      )}
                      {m.acknowledgement_sent && (
                        <span className="flex items-center gap-1 text-emerald-400">
                          <CheckCircle2 size={12} />
                          <span>Ack Sent</span>
                        </span>
                      )}
                      <span className="flex items-center gap-1">
                        <Clock size={12} />
                        <span>{formatToIST(m.received_at)}</span>
                      </span>
                    </div>
                  </div>

                  {/* Subject and Sender */}
                  <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
                    <div>
                      <h4 className="text-sm font-bold text-white">
                        {m.subject || '(No Subject)'}
                      </h4>
                      <p className="text-xs text-white/50 mt-0.5">
                        From: <span className="text-white/80">{m.sender_name ? `${m.sender_name} <${m.sender_email}>` : m.sender_email}</span>
                      </p>
                    </div>

                    <div className="flex items-center gap-2">
                      {m.processing_status === 'needs_review' && (
                        <div className="flex items-center gap-1.5">
                          <button
                            onClick={() => handleConfirmCivic(m.id)}
                            disabled={reviewingId === m.id}
                            className="text-xs bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-400 px-3 py-1.5 rounded-xl border border-emerald-500/30 font-semibold transition-all flex items-center gap-1 disabled:opacity-50"
                          >
                            <CheckCircle2 size={12} />
                            <span>Confirm Civic</span>
                          </button>
                          <button
                            onClick={() => handleMarkNonCivic(m.id)}
                            disabled={reviewingId === m.id}
                            className="text-xs bg-white/5 hover:bg-white/10 text-white/60 hover:text-white px-2.5 py-1.5 rounded-xl border border-white/10 transition-all flex items-center gap-1 disabled:opacity-50"
                          >
                            <X size={12} />
                            <span>Non-Civic</span>
                          </button>
                        </div>
                      )}
                      <button
                        onClick={() => setSelectedMessage(m)}
                        className="text-xs bg-white/5 hover:bg-white/10 text-white/80 hover:text-white px-3 py-1.5 rounded-xl border border-white/10 transition-all"
                      >
                        Inspect Extraction
                      </button>
                      {m.processing_status === 'failed' && (
                        <button
                          onClick={() => handleRetry(m.id)}
                          className="text-xs bg-rose-500/15 hover:bg-rose-500/25 text-rose-300 px-3 py-1.5 rounded-xl border border-rose-500/30 transition-all flex items-center gap-1"
                        >
                          <RotateCcw size={12} />
                          <span>Retry</span>
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Snippet / Description */}
                  <p className="text-xs text-white/60 line-clamp-2 leading-relaxed">
                    {m.snippet || m.body_plain}
                  </p>
                </div>
              )
            })}
          </div>
        )}

        {/* Message Detail Modal */}
        <AnimatePresence>
          {selectedMessage && (
            <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
              <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                className="bg-[#121316] border border-white/15 rounded-3xl max-w-2xl w-full p-6 sm:p-8 max-h-[85vh] overflow-y-auto space-y-5 shadow-2xl text-xs"
              >
                <div className="flex items-center justify-between border-b border-white/10 pb-4">
                  <div>
                    <span className="text-[10px] uppercase font-bold text-[#F36B21]">
                      Gmail Message #{selectedMessage.id}
                    </span>
                    <h3 className="text-lg font-bold text-white mt-0.5">
                      {selectedMessage.subject}
                    </h3>
                  </div>
                  <button
                    onClick={() => setSelectedMessage(null)}
                    className="p-1 rounded-full text-white/40 hover:text-white hover:bg-white/10"
                  >
                    <X size={18} />
                  </button>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-[#08090B] p-3 rounded-xl border border-white/5">
                    <span className="text-white/40 block text-[10px] uppercase">Sender</span>
                    <span className="text-white font-semibold">{selectedMessage.sender_email}</span>
                  </div>
                  <div className="bg-[#08090B] p-3 rounded-xl border border-white/5">
                    <span className="text-white/40 block text-[10px] uppercase">Received Time (IST)</span>
                    <span className="text-white font-medium">{formatToIST(selectedMessage.received_at)}</span>
                  </div>
                </div>

                {/* Gemini AI Extracted Insights */}
                <div className="bg-white/[0.02] border border-white/5 p-4 rounded-xl space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] uppercase font-bold text-[#F36B21] tracking-wider block">
                      Gemini AI Extraction Output
                    </span>
                    <button
                      onClick={() => handleReExtract(selectedMessage.id)}
                      disabled={reExtracting}
                      className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-[#F36B21]/15 text-[#F36B21] border border-[#F36B21]/30 hover:bg-[#F36B21]/25 transition text-[10px] font-semibold disabled:opacity-50"
                    >
                      <RefreshCw size={10} className={reExtracting ? 'animate-spin' : ''} />
                      {reExtracting ? 'Re-extracting...' : 'Re-extract Location'}
                    </button>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1">
                    <div>
                      <span className="text-white/40 block text-[10px]">Predicted Category</span>
                      <span className="text-white font-bold">{selectedMessage.extracted_category || 'N/A'}</span>
                    </div>
                    <div>
                      <span className="text-white/40 block text-[10px]">Extracted Landmark / Location</span>
                      <span className="text-white/90">{selectedMessage.extracted_location_text || 'Not explicitly provided'}</span>
                    </div>
                  </div>
                  {selectedMessage.extracted_metadata && (
                    <div className="mt-2 pt-2 border-t border-white/5">
                      <span className="text-white/40 block text-[10px] mb-1">Parsed JSON Structure:</span>
                      <pre className="bg-[#08090B] p-2.5 rounded-lg text-[10px] text-white/70 overflow-x-auto font-mono">
                        {JSON.stringify(JSON.parse(selectedMessage.extracted_metadata), null, 2)}
                      </pre>
                    </div>
                  )}
                </div>

                {/* Body Content */}
                <div>
                  <span className="text-white/40 block text-[10px] uppercase mb-1">Original Email Body</span>
                  <div className="bg-[#08090B] p-4 rounded-xl border border-white/5 max-h-48 overflow-y-auto whitespace-pre-wrap text-white/80 leading-relaxed font-sans">
                    {selectedMessage.body_plain || selectedMessage.snippet}
                  </div>
                </div>

                {/* Error if failed */}
                {selectedMessage.error_details && (
                  <div className="bg-rose-500/10 border border-rose-500/20 p-3 rounded-xl text-rose-300 text-xs">
                    <strong>Error / Note: </strong>{selectedMessage.error_details}
                  </div>
                )}

                {/* Admin Intake Actions */}
                <div className="flex flex-wrap items-center justify-end gap-2.5 pt-3 border-t border-white/10">
                  {selectedMessage.processing_status === 'needs_review' && (
                    <>
                      <button
                        onClick={() => handleMarkNonCivic(selectedMessage.id)}
                        disabled={reviewingId === selectedMessage.id}
                        className="px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-white/70 hover:text-white border border-white/10 font-semibold text-xs flex items-center gap-1.5 transition-all disabled:opacity-50"
                      >
                        <X size={14} />
                        <span>Confirm Non-Civic</span>
                      </button>
                      <button
                        onClick={() => handleConfirmCivic(selectedMessage.id)}
                        disabled={reviewingId === selectedMessage.id}
                        className="px-4 py-2 rounded-xl bg-emerald-500 text-white hover:bg-emerald-600 font-semibold text-xs flex items-center gap-1.5 shadow-lg shadow-emerald-500/20 transition-all disabled:opacity-50"
                      >
                        <CheckCircle2 size={14} />
                        <span>Promote to Civic Complaint</span>
                      </button>
                    </>
                  )}
                  {selectedMessage.complaint_id && (
                    <button
                      onClick={() => navigate(`/track?id=${selectedMessage.complaint_id}`)}
                      className="px-4 py-2 rounded-xl bg-[#F36B21] text-white hover:bg-[#E05D15] font-semibold text-xs flex items-center gap-1.5 transition-all"
                    >
                      <ExternalLink size={14} />
                      <span>View Complaint {selectedMessage.complaint_id}</span>
                    </button>
                  )}
                </div>
              </motion.div>
            </div>
          )}
        </AnimatePresence>
    </div>
  )

  if (isInternal) {
    return (
      <AuthorityLayout pageTitle="Gmail Intake Desk" breadcrumbs={['Admin', 'Gmail Intake']}>
        {renderContent()}
      </AuthorityLayout>
    )
  }

  return (
    <div className="min-h-screen bg-[#08090B] flex flex-col selection:bg-[#F36B21] selection:text-white">
      <Navbar />
      <main className="flex-1 max-w-7xl mx-auto w-full px-6 pt-32 pb-24">
        {renderContent()}
      </main>
      <Footer />
    </div>
  )
}

