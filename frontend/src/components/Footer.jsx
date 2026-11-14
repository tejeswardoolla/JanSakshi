import { Link } from 'react-router-dom'
import { ArrowRight, Shield } from 'lucide-react'

function FooterLinkGroup({ heading, links }) {
  return (
    <div>
      <h4 className="text-white/40 text-xs font-semibold tracking-widest uppercase mb-4">{heading}</h4>
      <ul className="space-y-3">
        {links.map((link) => (
          <li key={link.label}>
            {link.href.startsWith('#') ? (
              <button
                onClick={() => {
                  const el = document.querySelector(link.href)
                  if (el) el.scrollIntoView({ behavior: 'smooth' })
                }}
                className="text-white/50 hover:text-white text-sm transition-colors duration-200"
              >
                {link.label}
              </button>
            ) : (
              <Link to={link.href} className="text-white/50 hover:text-white text-sm transition-colors duration-200">
                {link.label}
              </Link>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}

export default function Footer() {
  return (
    <footer className="bg-[#08090B] border-t border-white/5 pt-16 pb-8">
      <div className="max-w-7xl mx-auto px-6">

        {/* Top row */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-12 mb-16">

          {/* Brand */}
          <div className="lg:col-span-1">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-12 h-12 rounded-full overflow-hidden border-2 border-[#F36B21]/30 flex-shrink-0">
                <img
                  src="/assets/jansakshi-logo.jpg"
                  alt="JanSakshi Logo"
                  className="w-full h-full object-cover"
                />
              </div>
              <div className="leading-tight">
                <span className="font-bold text-white text-lg">Jan</span>
                <span className="font-bold text-[#F36B21] text-lg">Sakshi</span>
              </div>
            </div>
            <p className="text-white/40 text-sm leading-relaxed mb-5 max-w-xs">
              An AI-powered civic intelligence platform making public infrastructure problems visible, verifiable and accountable.
            </p>
            <p className="text-white/25 text-xs font-medium tracking-wide">
              Citizen Reports. AI Verifies. Results Deliver.
            </p>
          </div>

          {/* Navigation */}
          <FooterLinkGroup
            heading="Platform"
            links={[
              { label: 'Home', href: '#hero' },
              { label: 'Our Mission', href: '#mission' },
              { label: 'How It Works', href: '#how-it-works' },
              { label: 'AI Intelligence', href: '#ai' },
              { label: 'Impact', href: '#equity' },
            ]}
          />

          {/* Project */}
          <FooterLinkGroup
            heading="Project"
            links={[
              { label: 'Report a Problem', href: '/report' },
              { label: 'Track Complaint', href: '/track' },
              { label: 'Official Authority Portal', href: '/authority' },
              { label: 'GitHub Repository', href: '#hero' },
            ]}
          />

          {/* Contact placeholder */}
          <div>
            <h4 className="text-white/40 text-xs font-semibold tracking-widest uppercase mb-4">Contact</h4>
            <p className="text-white/40 text-sm mb-2">
              This is a hackathon project. Contact details will be published in a future phase.
            </p>
            <div className="mt-4">
              <span className="inline-flex items-center gap-1 text-[#F36B21] text-xs font-semibold uppercase tracking-wider">
                Phase 1 Build
              </span>
            </div>

            {/* Large wordmark inspired by KINETIC */}
            <div className="mt-8">
              <Link to="/report">
                <button className="group flex items-center gap-2 bg-white/5 border border-white/10 text-white text-sm font-semibold px-5 py-3 rounded-full hover:bg-[#F36B21] hover:border-[#F36B21] transition-all duration-300">
                  Report Now
                  <ArrowRight size={14} className="group-hover:translate-x-1 transition-transform" />
                </button>
              </Link>
            </div>
          </div>
        </div>

        {/* Large wordmark */}
        <div className="border-t border-white/5 pt-8 relative overflow-hidden">
          <div
            className="text-[#F1F2F3]/[0.03] font-black text-[8rem] md:text-[14rem] leading-none select-none pointer-events-none absolute -bottom-10 left-0 right-0 text-center tracking-tighter"
          >
            jansakshi
          </div>

          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 relative z-10">
            <p className="text-white/25 text-xs">
              © 2026 JanSakshi. Hackathon Project. Phase 1–7.
            </p>
            <Link
              to="/authority"
              className="text-white/30 hover:text-[#F36B21] text-xs font-mono transition-colors flex items-center gap-1.5 px-3 py-1 rounded-full bg-white/[0.02] hover:bg-white/[0.05] border border-white/5"
            >
              <Shield size={11} className="text-[#F36B21]" />
              <span>Official Authority Portal (Admin Access)</span>
            </Link>
            <p className="text-white/25 text-xs">
              Built with React · FastAPI · AI for Civic Good
            </p>
          </div>
        </div>
      </div>
    </footer>
  )
}

