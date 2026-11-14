import React, { useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { UploadCloud, X, Film, Image as ImageIcon, AlertCircle, FileCheck } from 'lucide-react'

const MAX_IMAGE_SIZE_MB = 15
const MAX_VIDEO_SIZE_MB = 25
const ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp']
const ALLOWED_VIDEO_TYPES = ['video/mp4']

export default function EvidenceUploader({ files, onFilesChange, error }) {
  const fileInputRef = useRef(null)
  const [dragActive, setDragActive] = useState(false)
  const [localError, setLocalError] = useState(null)

  const videoCount = files.filter(f => f.file.type.startsWith('video/')).length

  const handleValidateAndAdd = (newFilesList) => {
    setLocalError(null)
    const validAdditions = []
    let currentVideos = videoCount

    for (const file of Array.from(newFilesList)) {
      const isVideo = file.type === 'video/mp4' || file.name.toLowerCase().endsWith('.mp4')
      const isImage = ALLOWED_IMAGE_TYPES.includes(file.type) || /\.(jpe?g|png|webp)$/i.test(file.name)

      if (!isImage && !isVideo) {
        setLocalError(`Unsupported file: "${file.name}". Supported formats: JPG, PNG, WEBP, MP4.`)
        continue
      }

      if (isVideo) {
        if (currentVideos >= 1) {
          setLocalError('A maximum of 1 video file (MP4) is allowed per complaint.')
          continue
        }
        if (file.size > MAX_VIDEO_SIZE_MB * 1024 * 1024) {
          setLocalError(`Video "${file.name}" exceeds maximum allowed size of ${MAX_VIDEO_SIZE_MB}MB.`)
          continue
        }
        currentVideos++
      } else {
        if (file.size > MAX_IMAGE_SIZE_MB * 1024 * 1024) {
          setLocalError(`Image "${file.name}" exceeds maximum allowed size of ${MAX_IMAGE_SIZE_MB}MB.`)
          continue
        }
      }

      const previewUrl = URL.createObjectURL(file)
      validAdditions.push({
        id: Math.random().toString(36).substring(2, 9),
        file,
        previewUrl,
        isVideo
      })
    }

    if (validAdditions.length > 0) {
      onFilesChange([...files, ...validAdditions])
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragActive(false)
    if (e.dataTransfer?.files) {
      handleValidateAndAdd(e.dataTransfer.files)
    }
  }

  const removeFile = (idToRemove) => {
    const fileToRemove = files.find(f => f.id === idToRemove)
    if (fileToRemove?.previewUrl) {
      URL.revokeObjectURL(fileToRemove.previewUrl)
    }
    onFilesChange(files.filter(f => f.id !== idToRemove))
  }

  return (
    <div className="space-y-4">
      {/* Upload Zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
        onDragLeave={() => setDragActive(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`relative border-2 border-dashed rounded-2xl p-6 sm:p-8 text-center cursor-pointer transition-all duration-200 ${
          dragActive
            ? 'border-[#F36B21] bg-[#F36B21]/10'
            : 'border-white/10 hover:border-white/20 bg-white/[0.02] hover:bg-white/[0.04]'
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".jpg,.jpeg,.png,.webp,.mp4,image/jpeg,image/png,image/webp,video/mp4"
          className="hidden"
          onChange={(e) => {
            if (e.target.files) handleValidateAndAdd(e.target.files)
            e.target.value = ''
          }}
        />

        <div className="w-12 h-12 mx-auto mb-3 rounded-2xl bg-[#F36B21]/15 text-[#F36B21] flex items-center justify-center">
          <UploadCloud size={24} />
        </div>

        <h4 className="text-white text-sm font-semibold mb-1">
          Click or Drag Photographic & Video Evidence
        </h4>
        <p className="text-white/40 text-xs max-w-sm mx-auto mb-3">
          Upload clear close-ups and wider situational shots of the damage. Max 15MB per photo (JPG, PNG, WEBP), max 1 video (MP4, up to 25MB).
        </p>

        <span className="inline-block bg-white/10 text-white/70 text-[11px] font-medium px-3 py-1 rounded-full">
          Browse Files
        </span>
      </div>

      {/* Error message */}
      <AnimatePresence>
        {(localError || error) && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="flex items-center gap-2 text-xs text-rose-400 bg-rose-500/10 border border-rose-500/20 p-3 rounded-xl"
          >
            <AlertCircle size={15} className="flex-shrink-0" />
            <span>{localError || error}</span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Uploaded Files Previews Grid */}
      {files.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs text-white/50 px-1">
            <span>Attached Evidence ({files.length})</span>
            <span>{videoCount}/1 Video</span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
            <AnimatePresence>
              {files.map((item) => (
                <motion.div
                  key={item.id}
                  layout
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.8 }}
                  className="relative group rounded-xl overflow-hidden border border-white/10 bg-[#121316] aspect-[4/3]"
                >
                  {item.isVideo ? (
                    <div className="w-full h-full flex flex-col items-center justify-center bg-black/60 p-2 text-center">
                      <Film size={28} className="text-[#F36B21] mb-1" />
                      <span className="text-[10px] text-white/70 truncate max-w-full px-1 font-mono">
                        {item.file.name}
                      </span>
                      <span className="text-[9px] text-[#F36B21] font-semibold uppercase mt-0.5">MP4 Video</span>
                    </div>
                  ) : (
                    <img
                      src={item.previewUrl}
                      alt={item.file.name}
                      className="w-full h-full object-cover"
                    />
                  )}

                  {/* Top bar with file size & delete */}
                  <div className="absolute inset-x-0 top-0 p-1.5 flex items-center justify-between bg-gradient-to-b from-black/80 to-transparent">
                    <span className="text-[9px] text-white/70 bg-black/50 px-1.5 py-0.5 rounded backdrop-blur-sm font-mono">
                      {(item.file.size / (1024 * 1024)).toFixed(1)}MB
                    </span>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation()
                        removeFile(item.id)
                      }}
                      className="w-5 h-5 rounded-full bg-rose-600 hover:bg-rose-500 text-white flex items-center justify-center transition-transform hover:scale-110 shadow"
                      title="Remove file"
                    >
                      <X size={12} />
                    </button>
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        </div>
      )}
    </div>
  )
}

