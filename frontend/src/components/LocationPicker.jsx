import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  MapPin,
  Crosshair,
  AlertTriangle,
  ExternalLink,
  Search,
  CheckCircle2,
  Navigation,
  Loader2
} from 'lucide-react'
import InteractiveLocationMap from './InteractiveLocationMap'

export default function LocationPicker({
  latitude,
  longitude,
  accuracy,
  locationSource,
  onLocationUpdate,
  error
}) {
  const [gpsLoading, setGpsLoading] = useState(false)
  const [gpsError, setGpsError] = useState(null)
  const [manualInput, setManualInput] = useState('')
  const [resolving, setResolving] = useState(false)
  const [resolveMessage, setResolveMessage] = useState(null)

  const handleUseGps = () => {
    if (!navigator.geolocation) {
      setGpsError('Geolocation is not supported by your browser.')
      return
    }

    setGpsLoading(true)
    setGpsError(null)

    const options = {
      enableHighAccuracy: true,
      timeout: 15000,
      maximumAge: 0,
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        const { latitude: lat, longitude: lng, accuracy: acc } = position.coords
        setGpsLoading(false)
        setGpsError(null)
        onLocationUpdate({
          latitude: Number(lat.toFixed(6)),
          longitude: Number(lng.toFixed(6)),
          accuracy: Math.round(acc),
          source: 'gps'
        })
      },
      (err) => {
        setGpsLoading(false)
        let msg = 'Failed to retrieve location.'
        switch (err.code) {
          case err.PERMISSION_DENIED:
            msg = 'Location permission denied. Please allow location access or type coordinates below.'
            break
          case err.POSITION_UNAVAILABLE:
            msg = 'Location position unavailable. Please check GPS connection.'
            break
          case err.TIMEOUT:
            msg = 'Location request timed out. Please try again or enter location manually.'
            break
          default:
            msg = err.message || 'Error capturing location.'
        }
        setGpsError(msg)
      },
      options
    )
  }

  const handleManualResolve = async (e) => {
    e?.preventDefault()
    if (!manualInput.trim()) return

    setResolving(true)
    setResolveMessage(null)

    try {
      const res = await fetch('/api/complaints/resolve-location', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: manualInput.trim() })
      })

      const data = await res.json()
      if (res.ok && data.success) {
        onLocationUpdate({
          latitude: Number(data.latitude.toFixed(6)),
          longitude: Number(data.longitude.toFixed(6)),
          accuracy: null,
          source: data.source
        })
        setResolveMessage({ type: 'success', text: `Resolved via ${data.source.replace('_', ' ')}.` })
      } else {
        setResolveMessage({
          type: 'error',
          text: data.message || 'Could not resolve location. Please verify format.'
        })
      }
    } catch (err) {
      setResolveMessage({
        type: 'error',
        text: 'Network error resolving location.'
      })
    } finally {
      setResolving(false)
    }
  }

  const handleMapPinChange = (lat, lng, source) => {
    onLocationUpdate({
      latitude: Number(lat.toFixed(6)),
      longitude: Number(lng.toFixed(6)),
      accuracy: accuracy,
      source: source
    })
  }

  const hasLocation = typeof latitude === 'number' && typeof longitude === 'number'
  const googleMapsUrl = hasLocation ? `https://www.google.com/maps?q=${latitude},${longitude}` : null

  return (
    <div className="space-y-4">
      {/* Primary Action: Use GPS */}
      <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center justify-between bg-white/[0.03] border border-white/10 p-4 rounded-2xl">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[#F36B21]/15 text-[#F36B21] flex items-center justify-center flex-shrink-0">
            <Navigation size={20} className={gpsLoading ? 'animate-spin' : ''} />
          </div>
          <div>
            <h4 className="text-white text-sm font-semibold">Incident Geolocation</h4>
            <p className="text-white/40 text-xs">
              Automated GPS accuracy ensures municipal field workers locate the exact physical issue.
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={handleUseGps}
          disabled={gpsLoading}
          className="flex items-center justify-center gap-2 bg-[#F36B21] hover:bg-[#F36B21]/90 text-white text-xs sm:text-sm font-semibold px-4 py-2.5 rounded-xl transition-all shadow-md shadow-[#F36B21]/20 disabled:opacity-50 whitespace-nowrap"
        >
          {gpsLoading ? (
            <>
              <Loader2 size={16} className="animate-spin" />
              <span>Locating...</span>
            </>
          ) : (
            <>
              <Crosshair size={16} />
              <span>Use My Current Location</span>
            </>
          )}
        </button>
      </div>

      {/* GPS Error alert */}
      <AnimatePresence>
        {gpsError && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="flex items-center gap-2.5 text-xs text-amber-300 bg-amber-500/10 border border-amber-500/20 p-3 rounded-xl"
          >
            <AlertTriangle size={16} className="flex-shrink-0" />
            <span>{gpsError}</span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Interactive Map */}
      <InteractiveLocationMap
        latitude={latitude}
        longitude={longitude}
        accuracy={accuracy}
        locationSource={locationSource}
        onLocationChange={handleMapPinChange}
      />

      {/* Location Details Pill & Warning when present */}
      {hasLocation && (
        <div className="space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-2 bg-[#121316] border border-white/10 px-4 py-3 rounded-xl text-xs">
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-white/40">Latitude: <strong className="text-white font-mono">{latitude}</strong></span>
              <span className="text-white/20">|</span>
              <span className="text-white/40">Longitude: <strong className="text-white font-mono">{longitude}</strong></span>
              {accuracy !== null && accuracy !== undefined && (
                <>
                  <span className="text-white/20">|</span>
                  <span className={`flex items-center gap-1 ${accuracy > 50 ? 'text-amber-400' : 'text-emerald-400'}`}>
                    <span>Accuracy: ~{accuracy}m</span>
                  </span>
                </>
              )}
              <span className="text-white/20">|</span>
              <span className="text-[#F36B21] uppercase text-[10px] tracking-wider font-semibold">
                Source: {locationSource.replace('_', ' ')}
              </span>
            </div>

            {googleMapsUrl && (
              <a
                href={googleMapsUrl}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-1 text-[#F36B21] hover:underline font-medium"
              >
                <span>Open in Google Maps</span>
                <ExternalLink size={12} />
              </a>
            )}
          </div>

          {/* Accuracy warning if > 50m */}
          {accuracy && accuracy > 50 && (
            <p className="text-[11px] text-amber-300/80 flex items-center gap-1 pl-1">
              <AlertTriangle size={12} />
              GPS accuracy is approximately {accuracy} meters. You can fine-tune the pin position by dragging the map marker.
            </p>
          )}
        </div>
      )}

      {/* Alternative Manual / Plus Code / Link Resolver */}
      <div className="bg-white/[0.02] border border-white/5 p-4 rounded-xl space-y-2">
        <label className="block text-xs font-medium text-white/60">
          Location Alternatives (Coordinates, Google Maps Link, or Plus Code)
        </label>
        <div className="flex gap-2">
          <div className="relative flex-1">
            <input
              type="text"
              value={manualInput}
              onChange={(e) => setManualInput(e.target.value)}
              placeholder="e.g. 17.3850, 78.4867 or https://maps.google.com/?q=... or 7J4V9F72+8M"
              className="w-full bg-[#08090B] border border-white/10 rounded-xl px-3.5 py-2.5 text-xs text-white placeholder-white/25 focus:outline-none focus:border-[#F36B21] transition-colors"
            />
          </div>
          <button
            type="button"
            onClick={handleManualResolve}
            disabled={resolving || !manualInput.trim()}
            className="flex items-center gap-1.5 bg-white/10 hover:bg-white/15 text-white text-xs font-semibold px-4 py-2.5 rounded-xl transition-all disabled:opacity-40 whitespace-nowrap"
          >
            {resolving ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />}
            <span>Locate</span>
          </button>
        </div>

        {resolveMessage && (
          <p
            className={`text-xs mt-1.5 flex items-center gap-1.5 ${
              resolveMessage.type === 'success' ? 'text-emerald-400' : 'text-rose-400'
            }`}
          >
            {resolveMessage.type === 'success' ? <CheckCircle2 size={13} /> : <AlertTriangle size={13} />}
            <span>{resolveMessage.text}</span>
          </p>
        )}
      </div>

      {error && (
        <p className="text-xs text-rose-400 flex items-center gap-1">
          <AlertTriangle size={13} />
          {error}
        </p>
      )}
    </div>
  )
}

