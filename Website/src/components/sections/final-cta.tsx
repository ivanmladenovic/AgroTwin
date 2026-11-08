import { Reveal } from '@/components/ui/reveal'
import { ButtonLink } from '@/components/ui/button'
import { APP_LOGIN_URL } from '@/lib/config'
import { useTranslation } from 'react-i18next'

export function FinalCtaSection() {
  const { t } = useTranslation()

  return (
    <section className="section-y">
      <div className="section-shell">
        <Reveal>
          <div className="relative overflow-hidden rounded-2xl border border-primary/15 sm:rounded-[1.75rem]">
            <div className="absolute inset-0" aria-hidden="true">
              <picture>
                <source srcSet="/assets/product/orchard-closing.webp" type="image/webp" />
                <img
                  src="/assets/product/orchard-closing.jpg"
                  alt=""
                  className="h-full w-full object-cover object-center"
                  loading="lazy"
                  decoding="async"
                />
              </picture>
              <div className="absolute inset-0 bg-primary/88" />
              <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_0%,rgba(46,179,190,0.28),transparent_40%),radial-gradient(circle_at_90%_100%,rgba(93,173,69,0.18),transparent_35%)]" />
            </div>
            <div className="relative px-5 py-10 text-center sm:px-10 sm:py-14">
              <div className="mx-auto max-w-2xl">
                <h2 className="text-[1.65rem] font-bold leading-tight tracking-tight text-white sm:text-3xl md:text-4xl">
                  {t('finalCta.title')}
                </h2>
                <p className="mt-3 text-[15px] leading-relaxed text-white/80 sm:mt-4 sm:text-base">
                  {t('finalCta.subtitle')}
                </p>
                <div className="mt-7 flex w-full flex-col items-stretch justify-center gap-3 sm:mt-8 lg:flex-row lg:items-center">
                  <ButtonLink
                    href={APP_LOGIN_URL}
                    className="w-full bg-white text-primary hover:bg-card lg:w-auto lg:min-w-[230px]"
                  >
                    {t('finalCta.primary')}
                  </ButtonLink>
                  <ButtonLink
                    href="#enterprise-contact"
                    variant="outline"
                    className="w-full border-white/30 text-white hover:bg-white hover:text-primary lg:w-auto lg:min-w-[230px]"
                  >
                    {t('finalCta.secondary')}
                  </ButtonLink>
                </div>
              </div>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  )
}
