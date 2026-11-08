import { Reveal } from '@/components/ui/reveal'
import { ButtonLink } from '@/components/ui/button'
import { APP_LOGIN_URL } from '@/lib/config'
import { useTranslation } from 'react-i18next'

export function HeroSection() {
  const { t } = useTranslation()

  return (
    <section id="top" className="relative isolate overflow-hidden border-b border-slate-800/60">
      <div className="ambient-glow" aria-hidden="true" />
      <div
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_70%_40%,rgba(16,185,129,0.08),transparent_55%)]"
        aria-hidden="true"
      />

      <div className="section-shell relative grid items-center gap-8 pb-12 pt-24 sm:gap-10 sm:pb-16 sm:pt-28 lg:min-h-[min(100svh,56rem)] lg:grid-cols-[1.05fr_0.95fr] lg:gap-12 lg:pb-24 lg:pt-32">
        <Reveal className="relative max-w-xl lg:max-w-none">
          <p className="kicker mb-5 hidden sm:inline-flex">{t('hero.kicker')}</p>
          <h1 className="text-gradient text-[1.75rem] font-extrabold leading-[1.12] sm:text-4xl md:text-[2.85rem] md:leading-[1.05] lg:text-[3.4rem]">
            {t('hero.title')}
          </h1>
          <p className="mt-4 max-w-lg text-[15px] leading-relaxed text-slate-300 sm:mt-6 sm:text-base md:text-lg">
            {t('hero.subtitle')}
          </p>
          <div className="mt-6 sm:mt-8">
            <ButtonLink href={APP_LOGIN_URL} className="w-full min-w-0 sm:w-auto sm:min-w-[210px]">
              {t('hero.primaryCta')}
            </ButtonLink>
          </div>
          <p className="mt-4 hidden text-sm leading-relaxed text-slate-400 sm:mt-5 sm:block">
            {t('hero.support')}
          </p>
        </Reveal>

        <Reveal delay={120} className="relative mx-auto w-full max-w-md sm:max-w-xl lg:mx-0 lg:max-w-none">
          <div
            className="pointer-events-none absolute -inset-4 rounded-[2rem] bg-[radial-gradient(ellipse_at_center,rgba(16,185,129,0.22),transparent_65%)] blur-2xl sm:-inset-8"
            aria-hidden="true"
          />
          <div className="hero-mock relative">
            <div className="relative overflow-hidden rounded-xl border border-emerald-500/30 bg-slate-950 shadow-[0_0_40px_-12px_rgba(16,185,129,0.35),0_28px_60px_-28px_rgba(0,0,0,0.85)] sm:rounded-2xl">
              <div className="pointer-events-none absolute inset-0 z-10 bg-gradient-to-br from-white/10 via-transparent to-emerald-500/10" />
              <div className="pointer-events-none absolute inset-x-0 top-0 z-10 h-16 bg-gradient-to-b from-white/10 to-transparent sm:h-24" />
              <picture>
                <source srcSet="/assets/orchard-dashboard-hero.webp" type="image/webp" />
                <img
                  src="/assets/orchard-dashboard-hero.jpg"
                  alt=""
                  className="aspect-[16/10] w-full object-cover object-center"
                  width={1024}
                  height={576}
                  fetchPriority="high"
                  decoding="async"
                />
              </picture>
            </div>
            <div
              className="pointer-events-none mx-auto mt-2 hidden h-8 w-[78%] rounded-[100%] bg-emerald-500/20 blur-2xl sm:mt-3 sm:block"
              aria-hidden="true"
            />
          </div>
        </Reveal>
      </div>
    </section>
  )
}
