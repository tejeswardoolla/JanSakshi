import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Menu, X, ArrowRight, Mail, Shield } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'

const navLinks = [
  { label: 'Home', href: '#hero' },
  { label: 'Our Mission', href: '#mission' },
  { label: 'How It Works', href: '#how-it-works' },
  { label: 'AI Intelligence', href: '#ai' },
  { label: 'Impact', href: '#equity' },
]

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 60)
    window.addEventListener('scroll', onScroll)
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  const scrollTo = (href) => {
    setMobileOpen(false)
    if (href.startsWith('#')) {
      const el = document.querySelector(href)
      if (el) el.scrollIntoView({ behavior: 'smooth' })
    }
  }

  return (
    <>
      <motion.nav
        initial={{ y: -80, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
        className={`fixed top-0 left-0 right-0 z-50 transition-all duration-500 ${
          scrolled
            ? 'bg-[#08090B]/90 backdrop-blur-xl border-b border-white/5 py-3'
            : 'bg-transparent py-5'
        }`}
      >
        <div className="max-w-7xl mx-auto px-6 flex items-center justify-between">
          {/* Left section: Logo + Name */}
          <div className="flex items-center gap-5">
            <Link to="/" className="flex items-center gap-3 group">
              <div className="w-10 h-10 rounded-full overflow-hidden border-2 border-[#F36B21]/40 group-hover:border-[#F36B21] transition-all duration-300 flex-shrink-0">
                <img
                  src="/assets/jansakshi-logo.jpg"
                  alt="JanSakshi Logo"
                  className="w-full h-full object-cover"
                />
              </div>
              <div className="leading-tight">
                <span className="font-bold text-white text-lg tracking-tight">Jan</span>
                <span className="font-bold text-[#F36B21] text-lg tracking-tight">Sakshi</span>
              </div>
            </Link>
          </div>

          {/* Desktop nav links */}
          <ul className="hidden md:flex items-center gap-8">
            {navLinks.map((link) => (
              <li key={link.label}>
                <button
                  onClick={() => scrollTo(link.href)}
                  className="text-sm text-white/70 hover:text-white transition-colors duration-200 font-medium relative group"
                >
                  {link.label}
                  <span className="absolute -bottom-0.5 left-0 w-0 h-px bg-[#F36B21] group-hover:w-full transition-all duration-300" />
                </button>
              </li>
            ))}
          </ul>

          {/* CTA */}
          <div className="hidden md:flex items-center gap-3">
            <button
              onClick={() => navigate('/track')}
              className="text-white/70 hover:text-white text-xs font-semibold px-4 py-2 rounded-full border border-white/10 hover:border-white/20 transition-all cursor-pointer"
            >
              Track Complaint
            </button>
            <button
              onClick={() => navigate('/report')}
              className="flex items-center gap-2 bg-[#F36B21] text-white text-sm font-semibold px-5 py-2 rounded-full hover:bg-[#F36B21]/90 hover:scale-105 active:scale-95 transition-all duration-200 cursor-pointer"
            >
              Report a Problem
              <ArrowRight size={14} />
            </button>
            <Link
              to="/authority/login?quick_access=true"
              className="flex items-center gap-2 px-3.5 py-2 rounded-full bg-[#102B4E]/90 hover:bg-[#102B4E] border border-[#F36B21]/50 hover:border-[#F36B21] shadow-lg shadow-[#102B4E]/40 text-xs font-semibold text-white/90 hover:text-white transition-all duration-200 group ml-1"
              title="Official Municipal Administration & Command Center"
            >
              <Shield className="w-3.5 h-3.5 text-[#F36B21] group-hover:scale-110 transition-transform" />
              <span>Official Authority Portal</span>
            </Link>
          </div>

          {/* Mobile hamburger */}
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            className="md:hidden text-white p-2"
            aria-label="Toggle menu"
          >
            {mobileOpen ? <X size={22} /> : <Menu size={22} />}
          </button>
        </div>
      </motion.nav>

      {/* Mobile menu */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.25 }}
            className="fixed top-[64px] left-0 right-0 z-40 bg-[#08090B]/95 backdrop-blur-xl border-b border-white/5 px-6 py-6 md:hidden"
          >
            <ul className="flex flex-col gap-5">
              <li className="pb-1 border-b border-white/10">
                <button
                  onClick={() => { setMobileOpen(false); navigate('/authority/login?quick_access=true') }}
                  className="w-full bg-[#102B4E] border border-[#F36B21]/50 text-white font-semibold py-2.5 rounded-xl text-center text-sm flex items-center justify-center gap-2 shadow-md"
                >
                  <Shield size={16} className="text-[#F36B21]" />
                  <span>Official Authority Portal</span>
                </button>
              </li>
              {navLinks.map((link) => (
                <li key={link.label}>
                  <button
                    onClick={() => scrollTo(link.href)}
                    className="text-white/80 hover:text-white text-lg font-medium w-full text-left"
                  >
                    {link.label}
                  </button>
                </li>
              ))}
              <li className="pt-2 flex flex-col gap-2">
                <button
                  onClick={() => { setMobileOpen(false); navigate('/track') }}
                  className="w-full text-white/80 border border-white/10 font-semibold py-2.5 rounded-full text-center text-sm"
                >
                  Track Complaint
                </button>
                <button
                  onClick={() => { setMobileOpen(false); navigate('/report') }}
                  className="w-full bg-[#F36B21] text-white font-semibold py-3 rounded-full text-center text-sm"
                >
                  Report a Problem
                </button>
              </li>
            </ul>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}

