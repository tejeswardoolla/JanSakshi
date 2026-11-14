import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Check, Copy, ExternalLink, ArrowRight, ShieldCheck, Clock, MapPin, Tag } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { formatToIST } from '../utils/dateTime'

export default function SubmissionSuccess({ data, onReset }) {
  const [copied, setCopied] = useState(false)
  const navigate = useNavigate()

  const copyId = () => {
    if (data?.complaint_id) {
      navigator.clipboard.writeText(data.complaint_id)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  const formattedDate = formatToIST(data?.created_at)

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className="max-w-2xl mx-auto bg-[#121316] border border-white/10 rounded-3xl p-6 sm:p-10 shadow-2xl space-y-8"
    >
      {/* Header with verified badge */}
      <div className="text-center space-y-3">
        <div className="w-16 h-16 mx-auto rounded-full bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
          <ShieldCheck size={32} />
        </div>
        <h2 className="text-white text-2xl sm:text-3xl font-extrabold tracking-tight">
          Your Report Has Been Received.
        </h2>
        <p className="text-white/50 text-sm max-w-md mx-auto">
          Thank you for being an active citizen. Your incident evidence and location have been registered into the JanSakshi civic registry.
        </p>
      </div>

      {/* Primary Key Card: Complaint ID */}
      <div className="bg-[#08090B] border border-white/15 rounded-2xl p-5 sm:p-6 text-center space-y-3">
        <span className="text-[11px] font-semibold tracking-widest uppercase text-white/40">
          Official Complaint Identifier
        </span>
        <div className="flex items-center justify-center gap-3">
          <span className="font-mono text-2xl sm:text-3xl font-black text-[#F36B21] tracking-wider">
            {data?.complaint_id || 'JS-2026-XXXXX'}
          </span>
          <button
            type="button"
            onClick={copyId}
            className="p-2 rounded-xl bg-white/10 hover:bg-white/15 text-white/80 hover:text-white transition-all"
            title="Copy Complaint ID"
          >
            {copied ? <Check size={18} className="text-emerald-400" /> : <Copy size={18} />}
          </button>
        </div>
        <AnimatePresence>
          {copied && (
            <motion.p
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="text-[11px] text-emerald-400 font-medium"
            >
              Copied to clipboard!
            </motion.p>
          )}
        </AnimatePresence>
      </div>

      {/* Incident Details Summary Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
        <div className="bg-white/[0.02] border border-white/5 p-4 rounded-xl space-y-1">
          <span className="text-white/40 flex items-center gap-1.5">
            <Tag size={13} className="text-[#F36B21]" /> Problem Category
          </span>
          <p className="text-white font-semibold text-sm">{data?.category}</p>
        </div>

        <div className="bg-white/[0.02] border border-white/5 p-4 rounded-xl space-y-1">
          <span className="text-white/40 flex items-center gap-1.5">
            <Clock size={13} className="text-[#138A4B]" /> Submission Timestamp
          </span>
          <p className="text-white font-medium">{formattedDate}</p>
        </div>

        <div className="bg-white/[0.02] border border-white/5 p-4 rounded-xl space-y-1 sm:col-span-2">
          <span className="text-white/40 flex items-center gap-1.5">
            <MapPin size={13} className="text-[#3B82F6]" /> Incident Coordinates & Map
          </span>
          <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
            <span className="text-white/70 font-mono">
              Status: <strong className="text-emerald-400 uppercase font-sans font-bold">{data?.status || 'Received'}</strong>
            </span>
            {data?.google_maps_url && (
              <a
                href={data.google_maps_url}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-1 text-[#F36B21] hover:underline font-medium"
              >
                <span>View Coordinates on Google Maps</span>
                <ExternalLink size={12} />
              </a>
            )}
          </div>
        </div>
      </div>

      {/* Truth in Civic AI note */}
      <div className="p-4 rounded-xl bg-white/[0.02] border border-white/5 text-[11px] text-white/40 leading-relaxed text-center">
        Note: The complaint has been securely queued. Future phases will incorporate AI evidence analysis, duplicate clustering, and automated municipal authority dispatch.
      </div>

      {/* Action Controls */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-2">
        <button
          type="button"
          onClick={() => navigate(`/track?id=${data?.complaint_id}`)}
          className="w-full sm:w-auto flex items-center justify-center gap-2 bg-[#F36B21] hover:bg-[#F36B21]/90 text-white font-semibold text-xs sm:text-sm px-6 py-3 rounded-full transition-all shadow-md shadow-[#F36B21]/20"
        >
          <span>Track Complaint Status</span>
          <ArrowRight size={14} />
        </button>

        <button
          type="button"
          onClick={onReset}
          className="w-full sm:w-auto px-5 py-3 rounded-full text-xs text-white/60 hover:text-white bg-white/5 hover:bg-white/10 transition-colors"
        >
          Report Another Problem
        </button>
      </div>
    </motion.div>
  )
}

