import { FadeUp } from '../animations/AnimationHelpers'
import { ArrowRight } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

export default function CTASection() {
  const navigate = useNavigate()

  const scrollToTop = () => {
    document.querySelector('#hero')?.scrollIntoView({ behavior: 'smooth' })
  }

  return (
    <section className="bg-[#F1F2F3] py-28 relative overflow-hidden">
      {/* Transition accent from dark */}
      <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-[#08090B]/10 to-transparent" />

      {/* Background orange glow */}
      <div className="absolute bottom-0 right-1/4 w-72 h-72 rounded-full bg-[#F36B21]/8 blur-[100px] pointer-events-none" />

      <div className="max-w-4xl mx-auto px-6 text-center relative z-10">
        <FadeUp>
          <span className="text-[#F36B21] text-xs font-semibold tracking-widest uppercase">Make Your Voice Count</span>
          <h2 className="text-display text-[#08090B] mt-5 mb-6">
            Your Voice.
            <br />
            <span className="text-[#F36B21]">Visible Change.</span>
          </h2>
          <p className="text-[#08090B]/55 text-lg leading-relaxed max-w-xl mx-auto mb-10">
            See a public problem? Help make it visible. Submit evidence and let JanSakshi help bring accountability.
          </p>
        </FadeUp>

        <FadeUp delay={0.2}>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <button
              onClick={() => navigate('/report')}
              className="group flex items-center gap-2 bg-[#F36B21] text-white font-semibold px-8 py-4 rounded-full hover:bg-[#F36B21]/90 hover:scale-105 active:scale-95 transition-all duration-200 text-base shadow-lg shadow-[#F36B21]/20"
            >
              Report a Problem
              <ArrowRight size={16} className="group-hover:translate-x-1 transition-transform" />
            </button>
            <button
              onClick={scrollToTop}
              className="text-[#08090B]/60 hover:text-[#08090B] font-medium underline underline-offset-4 transition-colors"
            >
              Discover Our Mission
            </button>
          </div>
        </FadeUp>

        {/* Tagline repeat */}
        <FadeUp delay={0.4}>
          <div className="mt-16 flex items-center justify-center gap-4 text-[#08090B]/30">
            {['Citizen Reports', 'AI Verifies', 'Results Deliver'].map((tag, i) => (
              <div key={tag} className="flex items-center gap-4">
                <span className="text-sm">{tag}</span>
                {i < 2 && <div className="w-1 h-1 rounded-full bg-[#F36B21]" />}
              </div>
            ))}
          </div>
        </FadeUp>
      </div>
    </section>
  )
}

