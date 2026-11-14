import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ArrowLeft,
  AlertCircle,
  Send,
  Loader2,
  Shield,
  FileText,
  User,
  Mail,
  Phone,
  CheckCircle2
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import CategorySelector from '../components/CategorySelector'
import LocationPicker from '../components/LocationPicker'
import EvidenceUploader from '../components/EvidenceUploader'
import SubmissionSuccess from '../components/SubmissionSuccess'

export default function ReportPage() {
  const navigate = useNavigate()

  // Form states
  const [category, setCategory] = useState('')
  const [description, setDescription] = useState('')
  const [location, setLocation] = useState({
    latitude: null,
    longitude: null,
    accuracy: null,
    source: 'gps'
  })
  const [evidenceFiles, setEvidenceFiles] = useState([])
  const [citizenInfo, setCitizenInfo] = useState({
    name: '',
    email: '',
    phone: ''
  })

  // Status & Validation
  const [errors, setErrors] = useState({})
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState(null)
  const [successData, setSuccessData] = useState(null)

  const handleLocationUpdate = (locData) => {
    setLocation(locData)
    if (errors.location) {
      setErrors((prev) => ({ ...prev, location: null }))
    }
  }

  const validate = () => {
    const newErrors = {}

    if (!category) {
      newErrors.category = 'Please select a problem category.'
    }

    const desc = description.trim()
    if (!desc) {
      newErrors.description = 'Please describe the problem.'
    } else if (desc.length < 10) {
      newErrors.description = `Description must be at least 10 characters (currently ${desc.length}).`
    } else if (desc.length > 2000) {
      newErrors.description = 'Description cannot exceed 2000 characters.'
    }

    if (location.latitude === null || location.longitude === null) {
      newErrors.location = 'Please capture your GPS location or specify coordinates on the map.'
    }

    if (citizenInfo.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(citizenInfo.email.trim())) {
      newErrors.email = 'Please enter a valid email address.'
    }

    if (citizenInfo.phone && !/^[0-9+\-\s()]{7,20}$/.test(citizenInfo.phone.trim())) {
      newErrors.phone = 'Please enter a valid phone number.'
    }

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (submitting) return // Prevent duplicate submission clicks

    if (!validate()) {
      // Scroll to top of form on validation error
      window.scrollTo({ top: 180, behavior: 'smooth' })
      return
    }

    setSubmitting(true)
    setSubmitError(null)

    try {
      const formData = new FormData()
      formData.append('category', category)
      formData.append('description', description.trim())
      formData.append('latitude', location.latitude)
      formData.append('longitude', location.longitude)
      if (location.accuracy !== null && location.accuracy !== undefined) {
        formData.append('location_accuracy', location.accuracy)
      }
      formData.append('location_source', location.source)

      if (citizenInfo.name?.trim()) {
        formData.append('citizen_name', citizenInfo.name.trim())
      }
      if (citizenInfo.email?.trim()) {
        formData.append('citizen_email', citizenInfo.email.trim())
      }
      if (citizenInfo.phone?.trim()) {
        formData.append('citizen_phone', citizenInfo.phone.trim())
      }

      for (const item of evidenceFiles) {
        formData.append('evidence', item.file)
      }

      const res = await fetch('/api/complaints/', {
        method: 'POST',
        body: formData
      })

      const data = await res.json()

      if (res.ok) {
        setSuccessData(data)
        window.scrollTo({ top: 80, behavior: 'smooth' })
      } else {
        setSubmitError(data.detail || 'An error occurred submitting your complaint. Please verify your data and retry.')
      }
    } catch (err) {
      setSubmitError('Unable to connect to the JanSakshi backend server. Please verify your connection or try again.')
    } finally {
      setSubmitting(false)
    }
  }

  const handleReset = () => {
    setCategory('')
    setDescription('')
    setLocation({ latitude: null, longitude: null, accuracy: null, source: 'gps' })
    setEvidenceFiles([])
    setCitizenInfo({ name: '', email: '', phone: '' })
    setErrors({})
    setSubmitError(null)
    setSuccessData(null)
  }

  return (
    <div className="min-h-screen bg-[#08090B] flex flex-col selection:bg-[#F36B21] selection:text-white">
      <Navbar />

      <main className="flex-1 max-w-4xl mx-auto w-full px-6 pt-32 pb-24">
        {/* Breadcrumb back navigation */}
        <button
          type="button"
          onClick={() => navigate('/')}
          className="flex items-center gap-2 text-white/40 hover:text-white text-xs mb-8 transition-colors group"
        >
          <ArrowLeft size={14} className="group-hover:-translate-x-1 transition-transform" />
          <span>Back to Overview</span>
        </button>

        {successData ? (
          <SubmissionSuccess data={successData} onReset={handleReset} />
        ) : (
          <div className="space-y-10">
            {/* Page Header */}
            <div>
              <div className="inline-flex items-center gap-2 bg-[#F36B21]/10 border border-[#F36B21]/20 rounded-full px-3 py-1 mb-3">
                <div className="w-1.5 h-1.5 rounded-full bg-[#F36B21] dot-blink" />
                <span className="text-[#F36B21] text-xs font-bold tracking-widest uppercase">
                  Citizen Portal · Phase 2
                </span>
              </div>
              <h1 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
                Report a Public Problem
              </h1>
              <p className="text-white/50 text-sm sm:text-base mt-2 max-w-2xl leading-relaxed">
                Help make your community safer and better. Share the problem, upload photographic evidence, and verify its exact location on the interactive map.
              </p>
            </div>

            {/* Submission Error Banner */}
            <AnimatePresence>
              {submitError && (
                <motion.div
                  initial={{ opacity: 0, y: -8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  className="flex items-start gap-3 bg-rose-500/15 border border-rose-500/30 text-rose-300 p-4 rounded-2xl text-sm"
                >
                  <AlertCircle size={20} className="flex-shrink-0 mt-0.5" />
                  <div className="space-y-1">
                    <p className="font-semibold">Submission Unsuccessful</p>
                    <p className="text-xs text-rose-300/80">{submitError}</p>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Main Form */}
            <form onSubmit={handleSubmit} className="space-y-10">
              {/* SECTION A: Category Selection */}
              <section className="bg-[#0E0E10] border border-white/10 rounded-3xl p-6 sm:p-8 space-y-4 shadow-xl">
                <div className="flex items-center justify-between border-b border-white/5 pb-4">
                  <div className="flex items-center gap-2.5">
                    <span className="w-6 h-6 rounded-full bg-[#F36B21]/20 text-[#F36B21] text-xs font-bold flex items-center justify-center">
                      1
                    </span>
                    <h3 className="text-white font-bold text-base">Select Problem Category</h3>
                  </div>
                  <span className="text-[11px] text-white/30 font-medium">* Required</span>
                </div>

                <CategorySelector
                  selectedCategory={category}
                  onSelect={(cat) => {
                    setCategory(cat)
                    if (errors.category) setErrors((prev) => ({ ...prev, category: null }))
                  }}
                  error={errors.category}
                />
              </section>

              {/* SECTION B: Description */}
              <section className="bg-[#0E0E10] border border-white/10 rounded-3xl p-6 sm:p-8 space-y-4 shadow-xl">
                <div className="flex items-center justify-between border-b border-white/5 pb-4">
                  <div className="flex items-center gap-2.5">
                    <span className="w-6 h-6 rounded-full bg-[#F36B21]/20 text-[#F36B21] text-xs font-bold flex items-center justify-center">
                      2
                    </span>
                    <h3 className="text-white font-bold text-base">Describe the Problem</h3>
                  </div>
                  <span className="text-[11px] text-white/30 font-medium">* Required</span>
                </div>

                <div className="space-y-2">
                  <textarea
                    rows={4}
                    value={description}
                    onChange={(e) => {
                      setDescription(e.target.value)
                      if (errors.description) setErrors((prev) => ({ ...prev, description: null }))
                    }}
                    maxLength={2000}
                    placeholder="Explain what happened, where you noticed it and how it affects the public..."
                    className="w-full bg-[#121316] border border-white/10 rounded-2xl p-4 text-sm text-white placeholder-white/25 focus:outline-none focus:border-[#F36B21] transition-colors resize-y min-h-[110px]"
                  />

                  <div className="flex items-center justify-between text-xs px-1">
                    {errors.description ? (
                      <p className="text-rose-400">{errors.description}</p>
                    ) : (
                      <p className="text-white/30">Minimum 10 characters.</p>
                    )}
                    <span className="text-white/40 font-mono">
                      {description.length} / 2000
                    </span>
                  </div>
                </div>
              </section>

              {/* SECTION C: Photo & Video Evidence */}
              <section className="bg-[#0E0E10] border border-white/10 rounded-3xl p-6 sm:p-8 space-y-4 shadow-xl">
                <div className="flex items-center justify-between border-b border-white/5 pb-4">
                  <div className="flex items-center gap-2.5">
                    <span className="w-6 h-6 rounded-full bg-[#F36B21]/20 text-[#F36B21] text-xs font-bold flex items-center justify-center">
                      3
                    </span>
                    <h3 className="text-white font-bold text-base">Photo & Video Evidence</h3>
                  </div>
                  <span className="text-[11px] text-white/30 font-medium">Recommended</span>
                </div>

                <EvidenceUploader
                  files={evidenceFiles}
                  onFilesChange={setEvidenceFiles}
                />
              </section>

              {/* SECTION D: Geolocation & Map */}
              <section className="bg-[#0E0E10] border border-white/10 rounded-3xl p-6 sm:p-8 space-y-4 shadow-xl">
                <div className="flex items-center justify-between border-b border-white/5 pb-4">
                  <div className="flex items-center gap-2.5">
                    <span className="w-6 h-6 rounded-full bg-[#F36B21]/20 text-[#F36B21] text-xs font-bold flex items-center justify-center">
                      4
                    </span>
                    <h3 className="text-white font-bold text-base">Incident Location</h3>
                  </div>
                  <span className="text-[11px] text-white/30 font-medium">* Required</span>
                </div>

                <LocationPicker
                  latitude={location.latitude}
                  longitude={location.longitude}
                  accuracy={location.accuracy}
                  locationSource={location.source}
                  onLocationUpdate={handleLocationUpdate}
                  error={errors.location}
                />
              </section>

              {/* SECTION E: Optional Citizen Information */}
              <section className="bg-[#0E0E10] border border-white/10 rounded-3xl p-6 sm:p-8 space-y-4 shadow-xl">
                <div className="flex items-center justify-between border-b border-white/5 pb-4">
                  <div className="flex items-center gap-2.5">
                    <span className="w-6 h-6 rounded-full bg-white/10 text-white/70 text-xs font-bold flex items-center justify-center">
                      5
                    </span>
                    <h3 className="text-white font-bold text-base">Citizen Details (Optional)</h3>
                  </div>
                  <span className="text-[11px] text-white/30 font-medium">Privacy Preserved</span>
                </div>

                <p className="text-xs text-white/40">
                  You are not required to provide personal info to report an issue. If supplied, details are kept confidential and used solely for municipal follow-up.
                </p>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2">
                  <div className="space-y-1.5">
                    <label className="text-xs text-white/60 font-medium flex items-center gap-1.5">
                      <User size={13} /> Your Name
                    </label>
                    <input
                      type="text"
                      value={citizenInfo.name}
                      onChange={(e) => setCitizenInfo((p) => ({ ...p, name: e.target.value }))}
                      placeholder="e.g. Ramesh Kumar"
                      className="w-full bg-[#121316] border border-white/10 rounded-xl px-3.5 py-2.5 text-xs text-white placeholder-white/20 focus:outline-none focus:border-[#F36B21] transition-colors"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs text-white/60 font-medium flex items-center gap-1.5">
                      <Mail size={13} /> Email Address
                    </label>
                    <input
                      type="email"
                      value={citizenInfo.email}
                      onChange={(e) => {
                        setCitizenInfo((p) => ({ ...p, email: e.target.value }))
                        if (errors.email) setErrors((prev) => ({ ...prev, email: null }))
                      }}
                      placeholder="e.g. ramesh@example.com"
                      className="w-full bg-[#121316] border border-white/10 rounded-xl px-3.5 py-2.5 text-xs text-white placeholder-white/20 focus:outline-none focus:border-[#F36B21] transition-colors"
                    />
                    {errors.email && <p className="text-[11px] text-rose-400">{errors.email}</p>}
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs text-white/60 font-medium flex items-center gap-1.5">
                      <Phone size={13} /> Phone Number
                    </label>
                    <input
                      type="tel"
                      value={citizenInfo.phone}
                      onChange={(e) => {
                        setCitizenInfo((p) => ({ ...p, phone: e.target.value }))
                        if (errors.phone) setErrors((prev) => ({ ...prev, phone: null }))
                      }}
                      placeholder="e.g. +91 98765 43210"
                      className="w-full bg-[#121316] border border-white/10 rounded-xl px-3.5 py-2.5 text-xs text-white placeholder-white/20 focus:outline-none focus:border-[#F36B21] transition-colors"
                    />
                    {errors.phone && <p className="text-[11px] text-rose-400">{errors.phone}</p>}
                  </div>
                </div>
              </section>

              {/* Submit CTA */}
              <div className="pt-4 flex flex-col sm:flex-row items-center justify-between gap-4">
                <div className="flex items-center gap-2 text-xs text-white/40">
                  <Shield size={14} className="text-[#138A4B]" />
                  <span>Secure Submission & Concurrency-Safe ID Generation</span>
                </div>

                <button
                  type="submit"
                  disabled={submitting}
                  className="w-full sm:w-auto flex items-center justify-center gap-2 bg-[#F36B21] hover:bg-[#F36B21]/90 text-white font-bold text-sm px-10 py-4 rounded-full transition-all shadow-xl shadow-[#F36B21]/25 hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50"
                >
                  {submitting ? (
                    <>
                      <Loader2 size={18} className="animate-spin" />
                      <span>Transmitting Report...</span>
                    </>
                  ) : (
                    <>
                      <span>Submit Complaint</span>
                      <Send size={16} />
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        )}
      </main>

      <Footer />
    </div>
  )
}
