import { useRef } from 'react'
import { motion } from 'framer-motion'
import { ArrowRight, ChevronDown } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { WordReveal } from '../animations/AnimationHelpers'

// Floating complaint card
function FloatingCard({ title, location, delay, className }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 1, ease: [0.16, 1, 0.3, 1] }}
      className={`absolute bg-white/5 backdrop-blur-md border border-white/10 rounded-2xl p-3.5 ${className}`}
      style={{ animation: `float ${3.5 + delay}s ease-in-out ${delay}s infinite` }}
    >
      <div className="flex items-center gap-2 mb-1">
        <div className="w-2 h-2 rounded-full bg-[#F36B21] dot-blink" />
        <span className="text-[#F36B21] text-xs font-semibold uppercase tracking-wider">Live Report</span>
      </div>
      <p className="text-white text-sm font-medium">{title}</p>
      <p className="text-white/40 text-xs mt-0.5">{location}</p>
    </motion.div>
  )
}

// Orange streak line
function Streak({ style, delay = 0 }) {
  return (
    <div
      className="absolute pointer-events-none overflow-hidden"
      style={style}
    >
      <div
        className="streak-h h-px bg-gradient-to-r from-transparent via-[#F36B21] to-transparent"
        style={{ width: '200px', animationDelay: `${delay}s`, opacity: 0.6 }}
      />
    </div>
  )
}

export default function HeroSection() {
  const navigate = useNavigate()

  const scrollToNext = () => {
    const el = document.querySelector('#carousel')
    if (el) el.scrollIntoView({ behavior: 'smooth' })
  }

  return (
    <section
      id="hero"
      className="relative min-h-screen bg-[#08090B] flex flex-col justify-center overflow-hidden"
    >
      {/* Background gradient glow */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/3 left-1/4 w-96 h-96 rounded-full bg-[#F36B21]/8 blur-[120px]" />
        <div className="absolute bottom-1/4 right-1/4 w-72 h-72 rounded-full bg-[#102B4E]/40 blur-[100px]" />
      </div>

      {/* Animated streaks */}
      <Streak style={{ top: '30%', left: 0, right: 0 }} delay={0} />
      <Streak style={{ top: '55%', left: 0, right: 0 }} delay={1.5} />
      <Streak style={{ top: '70%', left: 0, right: 0 }} delay={3} />

      {/* Grid pattern overlay */}
      <div
        className="absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage: 'linear-gradient(#F36B21 1px, transparent 1px), linear-gradient(90deg, #F36B21 1px, transparent 1px)',
          backgroundSize: '60px 60px',
        }}
      />

      {/* Floating cards */}
      <FloatingCard
        title="Pothole on MG Road"
        location="Ward 42 · Bangalore"
        delay={1.2}
        className="hidden lg:block top-1/4 right-16 w-52"
      />
      <FloatingCard
        title="Drainage Overflow"
        location="Ward 7 · Mumbai"
        delay={1.8}
        className="hidden lg:block bottom-1/3 right-28 w-48"
      />
      <FloatingCard
        title="Broken Streetlight"
        location="Ward 15 · Delhi"
        delay={2.4}
        className="hidden lg:block top-2/5 left-8 w-48"
      />

      {/* Main content */}
      <div className="relative z-10 max-w-7xl mx-auto px-6 pt-32 pb-20">
        {/* Eyebrow */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.3 }}
          className="flex items-center gap-3 mb-8"
        >
          <div className="flex items-center gap-2 bg-[#F36B21]/10 border border-[#F36B21]/20 rounded-full px-4 py-1.5">
            <div className="w-1.5 h-1.5 rounded-full bg-[#F36B21] dot-blink" />
            <span className="text-[#F36B21] text-xs font-semibold tracking-widest uppercase">
              AI-Powered Civic Intelligence
            </span>
          </div>
        </motion.div>

        {/* Headline */}
        <h1 className="text-display text-white mb-6 max-w-4xl">
          <WordReveal text="Every Problem" delay={0.4} />
          <br />
          <WordReveal text="Deserves" delay={0.6} className="text-white" />
          {' '}
          <WordReveal text="Attention." delay={0.8} className="text-[#F36B21]" />
        </h1>

        {/* Subtext */}
        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 1.1 }}
          className="text-subheading text-white/55 max-w-2xl mb-10"
        >
          An AI-powered civic intelligence platform making public problems
          visible, verifiable and accountable.
        </motion.p>

        {/* CTA Buttons */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 1.3 }}
          className="flex flex-wrap gap-4"
        >
          <button
            onClick={() => navigate('/report')}
            className="group flex items-center gap-2 bg-[#F36B21] text-white font-semibold px-7 py-4 rounded-full hover:bg-[#F36B21]/90 hover:scale-105 active:scale-95 transition-all duration-200 text-base"
          >
            Report a Problem
            <ArrowRight size={16} className="group-hover:translate-x-1 transition-transform" />
          </button>
          <button
            onClick={scrollToNext}
            className="group flex items-center gap-2 bg-white/5 border border-white/15 text-white font-semibold px-7 py-4 rounded-full hover:bg-white/10 hover:border-white/30 transition-all duration-200 text-base"
          >
            Explore JanSakshi
          </button>
        </motion.div>

        {/* Tagline */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1.8, duration: 1 }}
          className="mt-16 flex items-center gap-4"
        >
          {['Citizen Reports', 'AI Verifies', 'Results Deliver'].map((tag, i) => (
            <div key={tag} className="flex items-center gap-4">
              <span className="text-white/35 text-sm">{tag}</span>
              {i < 2 && <span className="w-1 h-1 rounded-full bg-[#F36B21] opacity-60" />}
            </div>
          ))}
        </motion.div>
      </div>

      {/* Scroll indicator */}
      <motion.button
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 2, duration: 1 }}
        onClick={scrollToNext}
        className="absolute bottom-10 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 text-white/30 hover:text-white/60 transition-colors"
      >
        <span className="text-xs tracking-widest uppercase font-medium">Scroll</span>
        <ChevronDown size={16} className="animate-bounce" />
      </motion.button>
    </section>
  )
}

