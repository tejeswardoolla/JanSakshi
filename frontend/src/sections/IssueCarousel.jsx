import { useState } from 'react'
import { motion } from 'framer-motion'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { FadeUp } from '../animations/AnimationHelpers'

const issueCategories = [
  {
    id: 1,
    title: 'Road Damage',
    description: 'Potholes, cracks, broken pavements and damaged road surfaces that endanger commuters.',
    image: '/assets/issues/road-damage.jpg',
    alt: 'Close-up of a large pothole on a wet urban Indian road with cracked asphalt edges',
    accent: '#F36B21',
    tag: 'Infrastructure',
  },
  {
    id: 2,
    title: 'Garbage Accumulation',
    description: 'Uncollected waste, overflowing bins and illegal dumping affecting public health.',
    image: '/assets/issues/garbage-accumulation.jpg',
    alt: 'Overflowing municipal garbage bins spilling waste onto a public street in India',
    accent: '#138A4B',
    tag: 'Sanitation',
  },
  {
    id: 3,
    title: 'Drainage Overflow',
    description: 'Blocked drains, stagnant water and sewage overflow creating health hazards.',
    image: '/assets/issues/drainage-overflow.jpg',
    alt: 'Murky drainage water overflowing from a clogged storm drain onto an urban road',
    accent: '#102B4E',
    tag: 'Drainage',
  },
  {
    id: 4,
    title: 'Water Leakage',
    description: 'Burst pipes, leaking mains and water wastage causing infrastructure damage.',
    image: '/assets/issues/water-leakage.jpg',
    alt: 'Burst underground water pipeline leaking onto a cracked public street',
    accent: '#3B82F6',
    tag: 'Water Supply',
  },
  {
    id: 5,
    title: 'Broken Streetlights',
    description: 'Non-functional street lighting that poses safety risks after dark.',
    image: '/assets/issues/broken-streetlight.jpg',
    alt: 'A damaged non-functional streetlight on a dim urban Indian street at dusk',
    accent: '#EAB308',
    tag: 'Lighting',
  },
]

function IssueCard({ item, isCenter }) {
  return (
    <motion.div
      whileHover={{ scale: isCenter ? 1.02 : 1.05, y: -6 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      className={`relative flex-shrink-0 rounded-3xl overflow-hidden cursor-pointer transition-all duration-500 ${
        isCenter
          ? 'w-72 md:w-80 shadow-2xl shadow-black/60 ring-1 ring-white/20'
          : 'w-56 md:w-64'
      }`}
    >
      {/* Image area */}
      <div className={`${isCenter ? 'h-52' : 'h-40'} relative overflow-hidden bg-[#1a1a1a]`}>
        <img
          src={item.image}
          alt={item.alt}
          className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105"
          style={{
            filter: isCenter
              ? 'brightness(0.92) contrast(1.05) saturate(0.95)'
              : 'brightness(0.55) contrast(1.0) saturate(0.7)',
          }}
          loading="lazy"
          onError={(e) => {
            // Fallback: hide broken image, show dark placeholder
            e.target.style.display = 'none'
            e.target.parentElement.style.background = '#1a1a1a'
          }}
        />

        {/* Gradient overlay at bottom of image */}
        <div
          className="absolute inset-0"
          style={{
            background: isCenter
              ? 'linear-gradient(to bottom, transparent 50%, rgba(8,9,11,0.5) 100%)'
              : 'linear-gradient(to bottom, transparent 40%, rgba(8,9,11,0.75) 100%)',
          }}
        />

        {/* Category tag – top left */}
        <div className="absolute top-3 left-3">
          <span
            className="text-[10px] font-bold tracking-widest uppercase px-2.5 py-1 rounded-full"
            style={{
              background: isCenter ? item.accent : 'rgba(255,255,255,0.1)',
              color: '#fff',
              backdropFilter: 'blur(8px)',
            }}
          >
            {item.tag}
          </span>
        </div>

        {/* Live indicator on center card */}
        {isCenter && (
          <div className="absolute top-3 right-3 flex items-center gap-1.5 bg-black/50 backdrop-blur-sm rounded-full px-2.5 py-1">
            <div className="w-1.5 h-1.5 rounded-full bg-[#F36B21] dot-blink" />
            <span className="text-white text-[10px] font-semibold">Reportable</span>
          </div>
        )}
      </div>

      {/* Card body */}
      <div
        className={`p-5 ${isCenter ? 'bg-white' : 'bg-[#111113] border-t border-white/5'}`}
      >
        {/* Accent line */}
        <div
          className="w-8 h-0.5 rounded-full mb-3 transition-all duration-300"
          style={{ background: isCenter ? item.accent : item.accent + '60' }}
        />
        <h3
          className={`font-bold text-lg mb-1.5 leading-tight ${
            isCenter ? 'text-[#08090B]' : 'text-white'
          }`}
        >
          {item.title}
        </h3>
        <p
          className={`text-sm leading-relaxed ${
            isCenter ? 'text-[#08090B]/55' : 'text-white/35'
          }`}
        >
          {item.description}
        </p>
      </div>
    </motion.div>
  )
}

export default function IssueCarousel() {
  const [active, setActive] = useState(0)
  const total = issueCategories.length

  const prev = () => setActive((a) => (a - 1 + total) % total)
  const next = () => setActive((a) => (a + 1) % total)

  // Visible slots: [−2, −1, 0, +1, +2]
  const getVisible = () =>
    [-2, -1, 0, 1, 2].map((offset) => ({
      item: issueCategories[(active + offset + total) % total],
      offset,
    }))

  return (
    <section id="carousel" className="bg-[#08090B] py-24 overflow-hidden">
      <div className="max-w-7xl mx-auto px-6">
        {/* Heading */}
        <FadeUp>
          <div className="mb-14">
            <span className="text-[#F36B21] text-xs font-semibold tracking-widest uppercase">
              Issues We Address
            </span>
            <h2 className="text-heading text-white mt-3 max-w-2xl">
              Problems Around Us.
              <br />
              <span className="text-white/35">Solutions Within Reach.</span>
            </h2>
          </div>
        </FadeUp>

        {/* Carousel track */}
        <div className="relative flex items-center justify-center gap-5 py-8 min-h-[420px]">
          {getVisible().map(({ item, offset }) => (
            <motion.div
              key={item.id}
              layout
              animate={{
                scale:
                  offset === 0 ? 1 : Math.abs(offset) === 1 ? 0.88 : 0.72,
                opacity:
                  offset === 0 ? 1 : Math.abs(offset) === 1 ? 0.65 : 0.3,
                zIndex:
                  offset === 0 ? 10 : Math.abs(offset) === 1 ? 5 : 1,
              }}
              transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
              onClick={() =>
                setActive((active + offset + total) % total)
              }
              className="cursor-pointer"
            >
              <IssueCard
                item={item}
                isCenter={offset === 0}
              />
            </motion.div>
          ))}
        </div>

        {/* Controls */}
        <FadeUp delay={0.3}>
          <div className="flex justify-center gap-3 mt-6">
            <button
              onClick={prev}
              className="w-12 h-12 rounded-full border border-white/15 flex items-center justify-center text-white hover:bg-white/10 hover:border-white/30 transition-all duration-200"
              aria-label="Previous issue"
            >
              <ChevronLeft size={18} />
            </button>
            <button
              onClick={next}
              className="w-12 h-12 rounded-full bg-[#F36B21] flex items-center justify-center text-white hover:bg-[#F36B21]/90 transition-all duration-200"
              aria-label="Next issue"
            >
              <ChevronRight size={18} />
            </button>
          </div>

          {/* Dot indicators */}
          <div className="flex justify-center gap-2 mt-5">
            {issueCategories.map((item, i) => (
              <button
                key={i}
                onClick={() => setActive(i)}
                className="transition-all duration-300 rounded-full"
                style={{
                  width: i === active ? '24px' : '6px',
                  height: '6px',
                  background: i === active ? '#F36B21' : 'rgba(255,255,255,0.2)',
                }}
                aria-label={`Go to ${item.title}`}
              />
            ))}
          </div>
        </FadeUp>
      </div>
    </section>
  )
}
