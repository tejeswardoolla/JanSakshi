import { motion } from 'framer-motion'
import { FadeUp } from '../animations/AnimationHelpers'
import { workflowSteps } from '../utils/constants'

function StepCard({ step, index }) {
  return (
    <FadeUp delay={index * 0.1}>
      <motion.div
        whileHover={{ y: -4, scale: 1.02 }}
        transition={{ duration: 0.25 }}
        className="relative bg-[#0E0E10] border border-white/8 rounded-2xl p-6 hover:border-white/20 transition-all duration-300 group"
      >
        {/* Number */}
        <div className="flex items-start justify-between mb-4">
          <span
            className="text-4xl font-black opacity-20 group-hover:opacity-40 transition-opacity duration-300"
            style={{ color: step.color }}
          >
            {step.number}
          </span>
          <span className="text-2xl">{step.icon}</span>
        </div>

        {/* Color line */}
        <div
          className="w-8 h-0.5 rounded-full mb-4 transition-all duration-300 group-hover:w-16"
          style={{ background: step.color }}
        />

        <h3 className="text-white font-bold text-lg mb-2">{step.title}</h3>
        <p className="text-white/40 text-sm leading-relaxed">{step.description}</p>

        {/* Connecting arrow (not on last) */}
        {index < workflowSteps.length - 1 && (
          <div className="hidden lg:block absolute -right-3 top-1/2 -translate-y-1/2 z-10">
            <div className="w-6 h-px bg-gradient-to-r from-white/20 to-transparent" />
          </div>
        )}
      </motion.div>
    </FadeUp>
  )
}

export default function HowItWorksSection() {
  return (
    <section id="how-it-works" className="bg-[#08090B] py-28 relative overflow-hidden">
      {/* Background accent */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-px h-24 bg-gradient-to-b from-[#F36B21]/40 to-transparent" />

      <div className="max-w-7xl mx-auto px-6">
        <FadeUp>
          <div className="text-center mb-16">
            <span className="text-[#F36B21] text-xs font-semibold tracking-widest uppercase">Platform Workflow</span>
            <h2 className="text-heading text-white mt-4 max-w-2xl mx-auto">
              From Citizen Voice to
              <br />
              <span className="text-white/40">Verified Action.</span>
            </h2>
            <p className="text-white/40 mt-4 max-w-xl mx-auto text-base">
              This is the intended platform workflow. Each phase is designed to transform a citizen report into documented, verifiable public action.
            </p>
          </div>
        </FadeUp>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {workflowSteps.map((step, i) => (
            <StepCard key={step.id} step={step} index={i} />
          ))}
        </div>

        {/* Disclaimer */}
        <FadeUp delay={0.5}>
          <div className="mt-10 text-center">
            <p className="text-white/25 text-xs max-w-xl mx-auto">
              Note: The above workflow represents the intended JanSakshi platform design. Full AI and backend capabilities will be implemented in subsequent phases.
            </p>
          </div>
        </FadeUp>
      </div>
    </section>
  )
}

