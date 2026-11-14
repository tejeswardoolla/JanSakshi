import React from 'react'
import { motion } from 'framer-motion'
import { Construction, Sparkles } from 'lucide-react'

export const COMPLAINT_CATEGORIES = [
  {
    id: 'Road Damage / Potholes',
    title: 'Road Damage / Potholes',
    image: '/assets/issues/road-damage.jpg',
    description: 'Potholes, cracked asphalt, missing paving slabs',
    accent: '#F36B21'
  },
  {
    id: 'Broken Streetlights',
    title: 'Broken Streetlights',
    image: '/assets/issues/broken-streetlight.jpg',
    description: 'Damaged fixtures, dark street segments, broken poles',
    accent: '#EAB308'
  },
  {
    id: 'Garbage Accumulation',
    title: 'Garbage Accumulation',
    image: '/assets/issues/garbage-accumulation.jpg',
    description: 'Overflowing dumpsters, public littering, illegal dumping',
    accent: '#138A4B'
  },
  {
    id: 'Drainage Overflow',
    title: 'Drainage Overflow',
    image: '/assets/issues/drainage-overflow.jpg',
    description: 'Blocked stormwater drains, open sewage overflow',
    accent: '#102B4E'
  },
  {
    id: 'Water Leakage',
    title: 'Water Leakage',
    image: '/assets/issues/water-leakage.jpg',
    description: 'Burst underground mains, leaking pipes, road pooling',
    accent: '#3B82F6'
  },
  {
    id: 'Damaged Public Infrastructure',
    title: 'Damaged Public Infrastructure',
    icon: Construction,
    description: 'Damaged bridges, cracked railings, damaged bus shelters',
    accent: '#8B5CF6'
  },
  {
    id: 'Other',
    title: 'Other',
    icon: Sparkles,
    description: 'Other municipal or civic infrastructure concerns',
    accent: '#6B7280'
  }
]

export default function CategorySelector({ selectedCategory, onSelect, error }) {
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
        {COMPLAINT_CATEGORIES.map((cat) => {
          const isSelected = selectedCategory === cat.id
          const IconComponent = cat.icon

          return (
            <motion.button
              type="button"
              key={cat.id}
              onClick={() => onSelect(cat.id)}
              whileHover={{ y: -2, scale: 1.01 }}
              whileTap={{ scale: 0.98 }}
              className={`relative text-left rounded-2xl overflow-hidden border p-3 flex flex-col justify-between transition-all duration-200 min-h-[140px] group ${
                isSelected
                  ? 'bg-white border-[#F36B21] shadow-lg shadow-[#F36B21]/15 ring-2 ring-[#F36B21]'
                  : 'bg-[#121316] border-white/10 hover:border-white/20'
              }`}
            >
              {/* Category visual */}
              {cat.image ? (
                <div className="relative w-full h-16 rounded-xl overflow-hidden mb-2 bg-[#1A1A1D]">
                  <img
                    src={cat.image}
                    alt={cat.title}
                    className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
                    style={{
                      filter: isSelected
                        ? 'brightness(0.95) contrast(1.05)'
                        : 'brightness(0.65) contrast(1.0)'
                    }}
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent" />
                </div>
              ) : (
                <div
                  className="w-full h-16 rounded-xl flex items-center justify-center mb-2 transition-colors"
                  style={{
                    background: isSelected ? `${cat.accent}20` : 'rgba(255,255,255,0.04)'
                  }}
                >
                  <IconComponent
                    size={26}
                    style={{ color: isSelected ? cat.accent : 'rgba(255,255,255,0.6)' }}
                  />
                </div>
              )}

              {/* Title & Desc */}
              <div>
                <h5
                  className={`text-xs font-bold leading-tight mb-0.5 ${
                    isSelected ? 'text-[#08090B]' : 'text-white'
                  }`}
                >
                  {cat.title}
                </h5>
                <p
                  className={`text-[11px] leading-snug line-clamp-2 ${
                    isSelected ? 'text-[#08090B]/60' : 'text-white/40'
                  }`}
                >
                  {cat.description}
                </p>
              </div>

              {/* Selection indicator pill */}
              {isSelected && (
                <div className="absolute top-2 right-2 w-2 h-2 rounded-full bg-[#F36B21]" />
              )}
            </motion.button>
          )
        })}
      </div>

      {error && (
        <p className="text-xs text-rose-400 pl-1">{error}</p>
      )}
    </div>
  )
}

