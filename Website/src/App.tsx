import { DocumentMeta } from '@/components/document-meta'
import { Footer } from '@/components/footer'
import { Navbar } from '@/components/navbar'
import { EnterpriseSection } from '@/components/sections/enterprise'
import { FaqSection } from '@/components/sections/faq'
import { FeaturesSection } from '@/components/sections/features'
import { HeroSection } from '@/components/sections/hero'
import { HowItWorksSection } from '@/components/sections/how-it-works'
import { PricingSection } from '@/components/sections/pricing'
import { ValueSection } from '@/components/sections/value'
import { useTranslation } from 'react-i18next'

export default function App() {
  const { t } = useTranslation()

  return (
    <div className="min-h-dvh overflow-x-clip bg-background text-foreground">
      <DocumentMeta />
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-[60] focus:rounded-lg focus:bg-primary focus:px-3 focus:py-2 focus:text-sm focus:text-primary-foreground"
      >
        {t('a11y.skip')}
      </a>
      <Navbar />
      <main id="main">
        <HeroSection />
        <ValueSection />
        <FeaturesSection />
        <PricingSection />
        <EnterpriseSection />
        <HowItWorksSection />
        <FaqSection />
      </main>
      <Footer />
    </div>
  )
}
