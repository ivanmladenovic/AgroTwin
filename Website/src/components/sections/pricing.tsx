import { Reveal } from '@/components/ui/reveal'
import { ButtonLink } from '@/components/ui/button'
import { SectionHeading } from '@/components/ui/section-heading'
import {
  ANNUAL_PRICE,
  ANNUAL_SAVINGS,
  MONTHLY_PRICE,
  licenseMailto,
} from '@/lib/config'
import { Check } from 'lucide-react'
import { useTranslation } from 'react-i18next'

export function PricingSection() {
  const { t } = useTranslation()
  const includes = t('pricing.includes', { returnObjects: true }) as string[]

  return (
    <section id="pricing" className="section-y relative">
      <div
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_50%_30%,rgba(16,185,129,0.1),transparent_55%)]"
        aria-hidden="true"
      />
      <div className="section-shell relative">
        <Reveal>
          <SectionHeading
            kicker={t('pricing.kicker')}
            title={t('pricing.title')}
            subtitle={t('pricing.subtitle')}
          />
        </Reveal>

        <div className="mx-auto mt-10 grid max-w-4xl gap-4 sm:mt-14 sm:gap-5 md:grid-cols-2">
          <Reveal>
            <article className="glass-card flex h-full flex-col p-4 sm:p-6">
              <p className="text-sm font-semibold text-slate-400">{t('pricing.monthly')}</p>
              <p className="mt-4 flex items-end gap-1">
                <span className="text-3xl font-extrabold text-white sm:text-4xl">{MONTHLY_PRICE}</span>
                <span className="pb-1 text-sm text-slate-500">{t('pricing.monthlyPeriod')}</span>
              </p>
              <p className="mt-2 text-sm text-slate-400">{t('pricing.monthlyBilling')}</p>
              <ul className="mt-6 flex-1 space-y-2.5">
                {includes.map((point) => (
                  <li key={point} className="flex gap-2 text-sm text-slate-300">
                    <Check className="mt-0.5 size-4 shrink-0 text-emerald-400" aria-hidden />
                    <span>{point}</span>
                  </li>
                ))}
              </ul>
              <ButtonLink href={licenseMailto('monthly')} variant="secondary" className="mt-8 w-full">
                {t('pricing.monthlyCta')}
              </ButtonLink>
            </article>
          </Reveal>

          <Reveal delay={90} className="pt-3">
            <article className="relative flex h-full flex-col rounded-2xl border border-emerald-500/40 bg-gradient-to-b from-emerald-500/15 via-slate-900/80 to-slate-950/90 p-4 shadow-[0_0_50px_-12px_rgba(16,185,129,0.45)] backdrop-blur-xl sm:p-6">
              <div
                className="pointer-events-none absolute inset-0 overflow-hidden rounded-2xl"
                aria-hidden="true"
              >
                <div className="absolute -right-10 -top-10 size-40 rounded-full bg-emerald-400/20 blur-3xl" />
              </div>
              <span className="absolute -top-3 left-4 z-10 inline-flex items-center rounded-full border border-emerald-400/40 bg-emerald-500 px-2.5 py-1 text-[10px] font-bold uppercase leading-none tracking-wide text-slate-950 shadow-[0_0_20px_rgba(16,185,129,0.5)] sm:left-6 sm:px-3 sm:text-[11px]">
                {t('pricing.recommended')}
              </span>
              <p className="relative text-sm font-semibold text-emerald-300/90">{t('pricing.annual')}</p>
              <p className="mt-4 flex items-end gap-1">
                <span className="text-3xl font-extrabold text-white sm:text-4xl">{ANNUAL_PRICE}</span>
                <span className="pb-1 text-sm text-slate-400">{t('pricing.annualPeriod')}</span>
              </p>
              <p className="mt-2 text-sm text-slate-400">{t('pricing.annualBilling')}</p>
              <p className="mt-2 text-sm font-semibold text-emerald-400">
                {t('pricing.savings', { amount: ANNUAL_SAVINGS })}
              </p>
              <ul className="mt-6 flex-1 space-y-2.5">
                {includes.map((point) => (
                  <li key={point} className="flex gap-2 text-sm text-slate-200">
                    <Check className="mt-0.5 size-4 shrink-0 text-emerald-400" aria-hidden />
                    <span>{point}</span>
                  </li>
                ))}
              </ul>
              <ButtonLink href={licenseMailto('annual')} className="mt-8 w-full">
                {t('pricing.annualCta')}
              </ButtonLink>
            </article>
          </Reveal>
        </div>
      </div>
    </section>
  )
}
