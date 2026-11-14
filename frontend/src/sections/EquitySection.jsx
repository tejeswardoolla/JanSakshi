import { FadeUp } from '../animations/AnimationHelpers'

function AreaCard({ title, label, description, issues, colorClass, bgClass }) {
  return (
    <div className={`rounded-3xl p-8 ${bgClass}`}>
      <div className={`inline-block text-xs font-bold tracking-widest uppercase px-3 py-1 rounded-full mb-5 ${colorClass}`}>
        {label}
      </div>
      <h3 className="text-white text-2xl font-bold mb-3">{title}</h3>
      <p className="text-white/50 text-sm leading-relaxed mb-6">{description}</p>
      <div className="space-y-2">
        {issues.map((issue) => (
          <div key={issue.label} className="flex items-center justify-between">
            <span className="text-white/60 text-sm">{issue.label}</span>
            <div className="flex items-center gap-2">
              <div className="w-24 h-1 bg-white/10 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-1000"
                  style={{ width: issue.width, background: issue.color }}
                />
              </div>
              <span className="text-white/40 text-xs w-6 text-right">{issue.count}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function EquitySection() {
  return (
    <section id="equity" className="bg-[#08090B] py-28 relative overflow-hidden">
      {/* Background element */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full bg-[#102B4E]/15 blur-[150px]" />
      </div>

      <div className="max-w-7xl mx-auto px-6 relative z-10">
        <FadeUp>
          <div className="text-center mb-16">
            <span className="text-[#138A4B] text-xs font-semibold tracking-widest uppercase">Equitable Governance</span>
            <h2 className="text-heading text-white mt-4 max-w-2xl mx-auto">
              Every Community
              <br />
              <span className="text-[#138A4B]">Deserves Attention.</span>
            </h2>
            <p className="text-white/40 mt-5 max-w-2xl mx-auto text-base leading-relaxed">
              Some areas may report fewer problems not because they have fewer issues, but because of limited digital access, low awareness or connectivity barriers. JanSakshi is designed to identify these gaps.
            </p>
          </div>
        </FadeUp>

        <div className="grid md:grid-cols-2 gap-6 max-w-4xl mx-auto">
          <FadeUp delay={0.1}>
            <AreaCard
              title="High-Reporting Ward"
              label="Well-Connected Area"
              description="Citizens here have good digital access and actively report infrastructure issues, creating a visible record of public problems."
              bgClass="bg-[#102B4E]/40 border border-[#102B4E]"
              colorClass="bg-[#102B4E] text-white"
              issues={[
                { label: 'Road Issues', width: '78%', color: '#F36B21', count: '78' },
                { label: 'Drainage', width: '62%', color: '#F36B21', count: '62' },
                { label: 'Lighting', width: '45%', color: '#F36B21', count: '45' },
              ]}
            />
          </FadeUp>
          <FadeUp delay={0.2}>
            <AreaCard
              title="Low-Reporting Ward"
              label="Potentially Underrepresented"
              description="Fewer complaints may mean limited digital access, not fewer problems. JanSakshi aims to flag these wards for proactive inspection."
              bgClass="bg-[#138A4B]/20 border border-[#138A4B]/40"
              colorClass="bg-[#138A4B]/30 text-[#138A4B]"
              issues={[
                { label: 'Road Issues', width: '18%', color: '#138A4B', count: '18' },
                { label: 'Drainage', width: '12%', color: '#138A4B', count: '12' },
                { label: 'Lighting', width: '8%', color: '#138A4B', count: '8' },
              ]}
            />
          </FadeUp>
        </div>

        <FadeUp delay={0.4}>
          <div className="mt-10 max-w-2xl mx-auto bg-white/5 border border-white/8 rounded-2xl p-6 text-center">
            <div className="flex items-center justify-center gap-2 mb-3">
              <span className="text-lg">⚖️</span>
              <span className="text-white font-semibold">Equity-Aware Design</span>
            </div>
            <p className="text-white/40 text-sm leading-relaxed">
              The data shown is illustrative. JanSakshi's equity analysis will use real reporting patterns to recommend proactive municipal inspections — helping ensure no community is left behind.
            </p>
          </div>
        </FadeUp>
      </div>
    </section>
  )
}

