import { ProductShot } from '@/components/showcase/product-shot'
import { Reveal } from '@/components/ui/reveal'
import { SectionHeading } from '@/components/ui/section-heading'
import { cn } from '@/lib/utils'
import { useTranslation } from 'react-i18next'

export function FeaturesSection() {
  const { t } = useTranslation()

  const features = [
    {
      id: 'digital-twin',
      kicker: t('features.digitalTwin.kicker'),
      title: t('features.digitalTwin.title'),
      description: t('features.digitalTwin.description'),
      points: t('features.digitalTwin.points', { returnObjects: true }) as string[],
      span: 'lg:col-span-2',
      shot: {
        webp: '/assets/product/ui-digital-twin.webp',
        jpg: '/assets/product/ui-digital-twin.jpg',
        alt: t('shots.digitalTwinAlt'),
      },
    },
    {
      id: 'satellite',
      kicker: t('features.satellite.kicker'),
      title: t('features.satellite.title'),
      description: t('features.satellite.description'),
      points: t('features.satellite.points', { returnObjects: true }) as string[],
      note: t('features.satellite.note'),
      span: 'lg:col-span-1',
      shot: {
        webp: '/assets/product/ui-satellite.webp',
        jpg: '/assets/product/ui-satellite.jpg',
        alt: t('shots.satelliteAlt'),
      },
    },
    {
      id: 'ai-agronomist',
      kicker: t('features.agronomist.kicker'),
      title: t('features.agronomist.title'),
      description: t('features.agronomist.description'),
      points: t('features.agronomist.points', { returnObjects: true }) as string[],
      note: t('features.agronomist.note'),
      span: 'lg:col-span-1',
      shot: {
        webp: '/assets/product/ui-agronomist.webp',
        jpg: '/assets/product/ui-agronomist.jpg',
        alt: t('shots.agronomistAlt'),
        portrait: true,
      },
    },
    {
      id: 'farm-management',
      kicker: t('features.farm.kicker'),
      title: t('features.farm.title'),
      description: t('features.farm.description'),
      points: t('features.farm.points', { returnObjects: true }) as string[],
      span: 'lg:col-span-2',
      shot: {
        webp: '/assets/product/ui-production.webp',
        jpg: '/assets/product/ui-production.jpg',
        alt: t('shots.productionAlt'),
      },
    },
  ]

  return (
    <section id="features" className="section-y relative border-y border-slate-800/70">
      <div
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_50%_0%,rgba(59,130,246,0.08),transparent_55%)]"
        aria-hidden="true"
      />
      <div className="section-shell relative">
        <Reveal>
          <SectionHeading
            kicker={t('features.kicker')}
            title={t('features.title')}
            subtitle={t('features.subtitle')}
            kickerTone="blue"
          />
        </Reveal>

        <div className="mt-12 grid gap-4 sm:mt-16 lg:grid-cols-3 lg:gap-5">
          {features.map((feature, index) => (
            <Reveal key={feature.id} delay={index * 50} className={cn('min-w-0', feature.span)}>
              <article
                id={feature.id}
                className="glass-card flex h-full min-w-0 flex-col overflow-hidden p-4 sm:p-6"
              >
                <p className="kicker mb-4 w-fit max-w-full">{feature.kicker}</p>
                <h3 className="text-lg font-bold text-white sm:text-2xl">{feature.title}</h3>
                <p className="mt-3 text-sm leading-relaxed text-slate-400 sm:text-[15px]">
                  {feature.description}
                </p>
                <ul className="mt-5 space-y-2">
                  {feature.points.map((point) => (
                    <li key={point} className="flex gap-3 text-sm text-slate-300">
                      <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-emerald-400" />
                      <span>{point}</span>
                    </li>
                  ))}
                </ul>
                {feature.note ? (
                  <p className="mt-5 rounded-xl border border-slate-700/70 bg-slate-950/50 px-4 py-3 text-xs leading-relaxed text-slate-400">
                    {feature.note}
                  </p>
                ) : null}
                <div className="mt-6 min-w-0 flex-1">
                  <ProductShot
                    title={feature.kicker}
                    webp={feature.shot.webp}
                    jpg={feature.shot.jpg}
                    alt={feature.shot.alt}
                    portrait={feature.shot.portrait}
                  />
                </div>
              </article>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  )
}
