import { Reveal } from '@/components/ui/reveal'
import { ButtonLink } from '@/components/ui/button'
import { SectionHeading } from '@/components/ui/section-heading'
import { ENTERPRISE_MAILTO } from '@/lib/config'
import { ChartColumnIncreasing, MapPinned, Users } from 'lucide-react'
import { useTranslation } from 'react-i18next'

export function HowItWorksSection() {
  const { t } = useTranslation()

  const steps = [
    {
      step: '01',
      title: t('how.steps.one.title'),
      description: t('how.steps.one.description'),
      icon: Users,
    },
    {
      step: '02',
      title: t('how.steps.two.title'),
      description: t('how.steps.two.description'),
      icon: MapPinned,
    },
    {
      step: '03',
      title: t('how.steps.three.title'),
      description: t('how.steps.three.description'),
      icon: ChartColumnIncreasing,
    },
  ]

  return (
    <section id="enterprise-pilot" className="section-y relative pt-8 sm:pt-10">
      <div className="section-shell relative">
        <Reveal>
          <SectionHeading
            kicker={t('how.kicker')}
            title={t('how.title')}
            subtitle={t('how.subtitle')}
          />
        </Reveal>

        <ol className="mt-12 grid gap-4 sm:mt-14 sm:gap-5 md:grid-cols-3">
          {steps.map((item, index) => (
            <Reveal key={item.step} delay={index * 80}>
              <li className="glass-card relative h-full p-4 sm:p-6">
                <div className="mb-4 flex items-center justify-between">
                  <span className="flex size-10 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/25 sm:size-11">
                    <item.icon className="size-5" aria-hidden />
                  </span>
                  <span className="font-mono text-sm font-medium text-sky-400">{item.step}</span>
                </div>
                <h3 className="text-lg font-bold text-white sm:text-xl">{item.title}</h3>
                <p className="mt-3 text-sm leading-relaxed text-slate-400">{item.description}</p>
              </li>
            </Reveal>
          ))}
        </ol>

        <Reveal>
          <div
            id="enterprise-contact"
            className="relative mx-auto mt-16 max-w-2xl overflow-hidden rounded-2xl border border-emerald-500/25 bg-gradient-to-b from-emerald-500/10 via-slate-900/70 to-slate-950/90 px-5 py-10 text-center shadow-[0_0_50px_-16px_rgba(16,185,129,0.4)] backdrop-blur-xl sm:mt-20 sm:px-10 sm:py-12"
          >
            <div
              className="pointer-events-none absolute -left-10 top-0 size-40 rounded-full bg-sky-500/15 blur-3xl"
              aria-hidden="true"
            />
            <h3 className="relative text-xl font-bold text-white sm:text-2xl md:text-3xl">
              {t('enterprise.discussTitle')}
            </h3>
            <p className="relative mx-auto mt-3 max-w-xl text-sm leading-relaxed text-slate-400 sm:text-base">
              {t('enterprise.discussBody')}
            </p>
            <ButtonLink
              href={ENTERPRISE_MAILTO}
              variant="enterprise"
              className="relative mt-7 w-full sm:mt-8 sm:w-auto sm:min-w-[240px]"
            >
              {t('enterprise.cta')}
            </ButtonLink>
          </div>
        </Reveal>
      </div>
    </section>
  )
}
