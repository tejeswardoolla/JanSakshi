import { useEffect, useRef } from 'react'
import { motion, useInView } from 'framer-motion'

// Reusable scroll-reveal wrapper
export function FadeUp({ children, delay = 0, className = '' }) {
  const ref = useRef(null)
  const inView = useInView(ref, { once: true, margin: '-80px' })
  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 40 }}
      animate={inView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.8, delay, ease: [0.16, 1, 0.3, 1] }}
      className={className}
    >
      {children}
    </motion.div>
  )
}

// Word-by-word reveal for headlines
export function WordReveal({ text, className = '', delay = 0 }) {
  const ref = useRef(null)
  const inView = useInView(ref, { once: true, margin: '-60px' })
  const words = text.split(' ')
  return (
    <span ref={ref} className={`inline ${className}`}>
      {words.map((word, i) => (
        <motion.span
          key={i}
          initial={{ opacity: 0, y: 30 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.6, delay: delay + i * 0.08, ease: [0.16, 1, 0.3, 1] }}
          className="inline-block mr-[0.25em]"
        >
          {word}
        </motion.span>
      ))}
    </span>
  )
}

// Orange light streak decoration
export function OrangeStreak({ className = '', delay = 0 }) {
  return (
    <div
      className={`absolute pointer-events-none overflow-hidden ${className}`}
    >
      <div
        className="streak-h h-px w-32 bg-gradient-to-r from-transparent via-[#F36B21] to-transparent opacity-80"
        style={{ animationDelay: `${delay}s` }}
      />
    </div>
  )
}

// Animated scanning frame for AI section
export function ScanFrame({ children, className = '' }) {
  return (
    <div className={`relative border border-[#F36B21]/30 rounded-lg overflow-hidden ${className}`}>
      {/* Corner accents */}
      <div className="absolute top-0 left-0 w-4 h-4 border-t-2 border-l-2 border-[#F36B21]" />
      <div className="absolute top-0 right-0 w-4 h-4 border-t-2 border-r-2 border-[#F36B21]" />
      <div className="absolute bottom-0 left-0 w-4 h-4 border-b-2 border-l-2 border-[#F36B21]" />
      <div className="absolute bottom-0 right-0 w-4 h-4 border-b-2 border-r-2 border-[#F36B21]" />
      {/* Scan line */}
      <div className="absolute inset-x-0 top-0 h-0.5 bg-gradient-to-r from-transparent via-[#F36B21] to-transparent scan-line opacity-70" />
      {children}
    </div>
  )
}

