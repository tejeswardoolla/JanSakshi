import Navbar from '../components/Navbar'
import HeroSection from '../sections/HeroSection'
import IssueCarousel from '../sections/IssueCarousel'
import MissionSection from '../sections/MissionSection'
import HowItWorksSection from '../sections/HowItWorksSection'
import AISection from '../sections/AISection'
import EquitySection from '../sections/EquitySection'
import CTASection from '../sections/CTASection'
import Footer from '../components/Footer'

export default function HomePage() {
  return (
    <div className="min-h-screen">
      <Navbar />
      <HeroSection />
      <IssueCarousel />
      <MissionSection />
      <HowItWorksSection />
      <AISection />
      <EquitySection />
      <CTASection />
      <Footer />
    </div>
  )
}

