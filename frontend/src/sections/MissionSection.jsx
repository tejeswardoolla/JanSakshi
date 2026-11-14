import { FadeUp, WordReveal, ScanFrame } from '../animations/AnimationHelpers'
import { ArrowRight } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

function StoryPill({ icon, label }) {
  return (
    <div className="flex items-center gap-2 bg-white border border-[#08090B]/8 rounded-full px-4 py-2 shadow-sm">
      <span className="text-lg">{icon}</span>
      <span className="text-[#08090B] text-sm font-medium">{label}</span>
    </div>
  )
}

export default function MissionSection() {
  const navigate = useNavigate()

  return (
    <section id="mission" className="bg-[#F1F2F3] py-28">
      <div className="max-w-7xl mx-auto px-6">
        <div className="grid lg:grid-cols-2 gap-16 items-center">
          {/* Left: text */}
          <div>
            <FadeUp>
              <span className="text-[#F36B21] text-xs font-semibold tracking-widest uppercase">Our Mission</span>
            </FadeUp>
            <FadeUp delay={0.1}>
              <h2 className="text-heading text-[#08090B] mt-4 mb-6">
                Making Communities
                <br />
                <span className="text-[#F36B21]">Visible.</span>
              </h2>
            </FadeUp>
            <FadeUp delay={0.2}>
              <p className="text-[#08090B]/60 text-lg leading-relaxed mb-8 max-w-lg">
                Public problems should never remain invisible. JanSakshi connects
                citizen reports, AI-powered evidence analysis and accountable
                public action in one platform.
              </p>
            </FadeUp>
            <FadeUp delay={0.3}>
              <p className="text-[#08090B]/50 text-base leading-relaxed mb-10 max-w-lg">
                We believe every pothole, every broken light, every overflowing
                drain deserves to be seen, verified and acted upon — regardless
                of which ward it is in or who lives there.
              </p>
            </FadeUp>
            <FadeUp delay={0.4}>
              <button
                onClick={() => navigate('/report')}
                className="group flex items-center gap-2 bg-[#08090B] text-white font-semibold px-7 py-4 rounded-full hover:bg-[#102B4E] transition-all duration-200"
              >
                Start Reporting
                <ArrowRight size={16} className="group-hover:translate-x-1 transition-transform" />
              </button>
            </FadeUp>
          </div>

          {/* Right: visual storytelling */}
          <FadeUp delay={0.3} className="relative">
            <div className="relative">
              {/* Main scan frame */}
              <ScanFrame className="bg-white p-6 rounded-3xl shadow-xl">
                <div className="grid grid-cols-2 gap-4">
                  {/* Citizen reporting */}
                  <div className="bg-[#F1F2F3] rounded-2xl p-4 flex flex-col items-center text-center gap-2">
                    <span className="text-3xl">📱</span>
                    <p className="text-[#08090B] text-xs font-semibold">Citizen Report</p>
                    <div className="w-full h-1 bg-[#F36B21]/20 rounded-full overflow-hidden">
                      <div className="h-full w-3/4 bg-[#F36B21] rounded-full" />
                    </div>
                  </div>
                  {/* Location pin */}
                  <div className="bg-[#102B4E]/8 rounded-2xl p-4 flex flex-col items-center text-center gap-2">
                    <span className="text-3xl">📍</span>
                    <p className="text-[#08090B] text-xs font-semibold">GPS Located</p>
                    <div className="w-full h-1 bg-[#102B4E]/20 rounded-full overflow-hidden">
                      <div className="h-full w-full bg-[#102B4E] rounded-full" />
                    </div>
                  </div>
                  {/* AI verification */}
                  <div className="bg-[#138A4B]/8 rounded-2xl p-4 flex flex-col items-center text-center gap-2">
                    <span className="text-3xl">🤖</span>
                    <p className="text-[#08090B] text-xs font-semibold">AI Verified</p>
                    <div className="w-full h-1 bg-[#138A4B]/20 rounded-full overflow-hidden">
                      <div className="h-full w-2/3 bg-[#138A4B] rounded-full" />
                    </div>
                  </div>
                  {/* Authority action */}
                  <div className="bg-[#F36B21]/8 rounded-2xl p-4 flex flex-col items-center text-center gap-2">
                    <span className="text-3xl">🏛️</span>
                    <p className="text-[#08090B] text-xs font-semibold">Authority Alerted</p>
                    <div className="w-full h-1 bg-[#F36B21]/20 rounded-full overflow-hidden">
                      <div className="h-full w-1/2 bg-[#F36B21] rounded-full" />
                    </div>
                  </div>
                </div>

                {/* Platform tagline in card */}
                <div className="mt-4 bg-[#08090B] rounded-xl px-4 py-3 flex items-center justify-between">
                  <span className="text-white text-xs font-medium">JanSakshi Platform</span>
                  <div className="flex gap-1">
                    <div className="w-1.5 h-1.5 rounded-full bg-[#F36B21] dot-blink" />
                    <span className="text-white/40 text-xs">Active</span>
                  </div>
                </div>
              </ScanFrame>

              {/* Floating story pills */}
              <div className="absolute -bottom-6 -left-6 flex flex-col gap-2">
                <StoryPill icon="📸" label="Evidence Captured" />
                <StoryPill icon="⚡" label="Priority Assigned" />
              </div>
            </div>
          </FadeUp>
        </div>
      </div>
    </section>
  )
}

