import React, { useEffect, useRef } from 'react'
import { MapContainer, TileLayer, Marker, useMapEvents, useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { Crosshair, MapPin } from 'lucide-react'

// Fix Leaflet's default icon missing in bundlers like Vite
const customMarkerIcon = new L.Icon({
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
})

function MapClickHandler({ onLocationChange }) {
  useMapEvents({
    click(e) {
      onLocationChange(e.latlng.lat, e.latlng.lng, 'map_click')
    },
  })
  return null
}

function MapRecenter({ lat, lng }) {
  const map = useMap()
  useEffect(() => {
    if (lat && lng) {
      map.setView([lat, lng], 16, { animate: true })
    }
  }, [lat, lng, map])
  return null
}

export default function InteractiveLocationMap({
  latitude,
  longitude,
  accuracy,
  locationSource,
  onLocationChange,
}) {
  const hasCoordinates = typeof latitude === 'number' && typeof longitude === 'number' && !isNaN(latitude) && !isNaN(longitude)
  const defaultPosition = [20.5937, 78.9629] // Center of India fallback for initial camera view if not set

  return (
    <div className="relative rounded-2xl overflow-hidden border border-white/10 bg-[#0E0E10] shadow-inner">
      {hasCoordinates ? (
        <div className="relative h-72 sm:h-80 w-full z-0">
          <MapContainer
            center={[latitude, longitude]}
            zoom={16}
            scrollWheelZoom={false}
            className="h-full w-full"
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> contributors'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <Marker
              position={[latitude, longitude]}
              icon={customMarkerIcon}
              draggable={true}
              eventHandlers={{
                dragend: (e) => {
                  const marker = e.target
                  const position = marker.getLatLng()
                  onLocationChange(position.lat, position.lng, 'marker_drag')
                },
              }}
            />
            <MapClickHandler onLocationChange={onLocationChange} />
            <MapRecenter lat={latitude} lng={longitude} />
          </MapContainer>

          {/* Quick interactive hint badge */}
          <div className="absolute top-3 right-3 z-[1000] bg-[#08090B]/85 backdrop-blur-md border border-white/10 px-3 py-1.5 rounded-full flex items-center gap-1.5 shadow-md pointer-events-none">
            <Crosshair size={13} className="text-[#F36B21] animate-pulse" />
            <span className="text-[11px] text-white/80 font-medium">Click map or drag pin to adjust</span>
          </div>
        </div>
      ) : (
        <div className="h-72 sm:h-80 w-full flex flex-col items-center justify-center p-6 text-center bg-gradient-to-b from-[#141416] to-[#0A0B0D]">
          <div className="w-14 h-14 rounded-2xl bg-[#F36B21]/10 border border-[#F36B21]/20 flex items-center justify-center text-[#F36B21] mb-4">
            <MapPin size={28} />
          </div>
          <h4 className="text-white font-semibold text-base mb-1">No Location Selected</h4>
          <p className="text-white/40 text-xs sm:text-sm max-w-sm">
            Use the "Use My Current Location" button above, or enter coordinates/maps link below to plot the incident location on the interactive map.
          </p>
        </div>
      )}
    </div>
  )
}

