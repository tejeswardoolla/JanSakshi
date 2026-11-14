import { motion } from 'framer-motion'
import { FadeUp, ScanFrame } from '../animations/AnimationHelpers'
import { aiCapabilities } from '../utils/constants'

function CapabilityCard({ item, index }) {
  return (
    <FadeUp delay={index * 0.08}>
      <motion.div
        whileHover={{ y: -4, borderColor: 'rgba(243,107,33,0.3)' }}
        transition={{ duration: 0.25 }}
        className="bg-[#F1F2F3] border border-transparent rounded-2xl p-5 group cursor-default"
      >
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 rounded-xl bg-white flex items-center justify-center text-xl flex-shrink-0 shadow-sm">
            {item.icon}
          </div>
          <div>
            <h3 className="text-[#08090B] font-bold text-base mb-1">{item.title}</h3>
            <p className="text-[#08090B]/50 text-sm leading-relaxed">{item.description}</p>
          </div>
        </div>
      </motion.div>
    </FadeUp>
  )
}

function AIScanVisual() {
  return (
    <div className="relative">
      <ScanFrame className="bg-[#08090B] p-6 rounded-3xl">
        {/* AI label */}
        <div className="flex items-center gap-2 mb-5">
          <div className="w-2 h-2 rounded-full bg-[#F36B21] dot-blink" />
          <span className="text-[#F36B21] text-xs font-semibold tracking-widest uppercase">AI Processing</span>
        </div>

        {/* Image scan area */}
        <div className="relative bg-[#141416] rounded-xl h-40 mb-4 overflow-hidden flex items-center justify-center">
          <span className="text-6xl opacity-30">🛣️</span>
          {/* Scan overlay */}
          <div className="absolute inset-0 bg-gradient-to-b from-[#F36B21]/10 to-transparent scan-line" />
          {/* Detection boxes */}
          <div className="absolute top-4 left-6 w-16 h-10 border border-[#F36B21]/60 rounded" />
          <div className="absolute bottom-4 right-8 w-12 h-8 border border-[#138A4B]/60 rounded" />
        </div>

        {/* Analysis output */}
        <div className="space-y-2.5">
          {[
            { label: 'Issue Detected', value: 'Road Damage – Pothole', color: '#F36B21', w: '90%' },
            { label: 'Confidence', value: '94.2%', color: '#138A4B', w: '94%' },
            { label: 'Duplicate Check', value: 'No Match Found', color: '#3B82F6', w: '60%' },
            { label: 'Priority Score', value: 'High', color: '#F36B21', w: '75%' },
          ].map((row) => (
            <div key={row.label} className="flex items-center justify-between gap-3">
              <span className="text-white/40 text-xs w-28 flex-shrink-0">{row.label}</span>
              <div className="flex-1 h-1 bg-white/5 rounded-full overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: row.w }}
                  transition={{ duration: 1.2, ease: [0.16, 1, 0.3, 1] }}
                  className="h-full rounded-full"
                  style={{ background: row.color }}
                />
              </div>
              <span className="text-white text-xs font-medium w-24 text-right">{row.value}</span>
            </div>
          ))}
        </div>
      </ScanFrame>

      {/* Floating badge */}
      <div className="absolute -bottom-4 -right-4 bg-[#F36B21] text-white text-xs font-bold px-3 py-1.5 rounded-full shadow-lg shadow-[#F36B21]/30">
        Intended Capability
      </div>
    </div>
  )
}

export default function AISection() {
  return (
    <section id="ai" className="bg-[#F1F2F3] py-28">
      <div className="max-w-7xl mx-auto px-6">
        <div className="grid lg:grid-cols-2 gap-16 items-start">
          {/* Left: capabilities */}
          <div>
            <FadeUp>
              <span className="text-[#F36B21] text-xs font-semibold tracking-widest uppercase">AI Intelligence</span>
              <h2 className="text-heading text-[#08090B] mt-4 mb-4">
                Beyond Complaint
                <br />
                <span className="text-[#F36B21]">Collection.</span>
              </h2>
              <p className="text-[#08090B]/55 text-base leading-relaxed mb-10">
                JanSakshi is designed with AI at its core — not to manage forms, but to genuinely understand, verify and prioritize public infrastructure problems.
              </p>
            </FadeUp>

            <div className="grid gap-3">
              {aiCapabilities.map((item, i) => (
                <CapabilityCard key={item.title} item={item} index={i} />
              ))}
            </div>
          </div>

          {/* Right: AI visual */}
          <FadeUp delay={0.3} className="lg:sticky lg:top-28">
            <AIScanVisual />
          </FadeUp>
        </div>
      </div>
    </section>
  )
}

