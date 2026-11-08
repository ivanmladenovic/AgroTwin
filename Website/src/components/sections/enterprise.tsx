import { Reveal } from '@/components/ui/reveal'
import { SectionHeading } from '@/components/ui/section-heading'
import {
  Bot,
  Building2,
  Network,
  Radar,
  Settings2,
  ShieldCheck,
} from 'lucide-react'
import { useTranslation } from 'react-i18next'

export function EnterpriseSection() {
  const { t } = useTranslation()

  const capabilities = [
    {
      key: 'multiFarm',
      icon: Building2,
      points: t('enterprise.capabilities.multiFarm.points', { returnObjects: true }) as string[],
    },
    {
      key: 'network',
      icon: Network,
      points: t('enterprise.capabilities.network.points', { returnObjects: true }) as string[],
    },
    {
      key: 'intelligence',
      icon: Radar,
      points: t('enterprise.capabilities.intelligence.points', { returnObjects: true }) as string[],
    },
    {
      key: 'ai',
      icon: Bot,
      points: t('enterprise.capabilities.ai.points', { returnObjects: true }) as string[],
    },
    {
      key: 'integrations',
      icon: Settings2,
      points: t('enterprise.capabilities.integrations.points', { returnObjects: true }) as string[],
    },
    {
      key: 'scale',
      icon: ShieldCheck,
      points: t('enterprise.capabilities.scale.points', { returnObjects: true }) as string[],
    },
  ] as const

  return (
    <section id="enterprise" className="section-y relative">
      <div className="ambient-glow" aria-hidden="true" />
      <div className="section-shell relative">
        <Reveal>
          <SectionHeading
            kicker={t('enterprise.kicker')}
            title={t('enterprise.title')}
            subtitle={t('enterprise.subtitle')}
            kickerTone="blue"
          />
          <p className="mx-auto mt-5 max-w-3xl text-center text-sm leading-relaxed text-slate-400 sm:text-base">
            {t('enterprise.intro')}
          </p>
        </Reveal>

        <div className="mt-12 grid gap-4 sm:mt-14 sm:grid-cols-2 sm:gap-5 lg:grid-cols-3">
          {capabilities.map((item, index) => (
            <Reveal key={item.key} delay={index * 45}>
              <article className="glass-card h-full p-4 sm:p-6">
                <div className="mb-4 flex size-11 items-center justify-center rounded-xl bg-sky-500/10 text-sky-400 ring-1 ring-sky-500/20">
                  <item.icon className="size-5" aria-hidden />
                </div>
                <h3 className="text-lg font-semibold text-white">
                  {t(`enterprise.capabilities.${item.key}.title`)}
                </h3>
                <ul className="mt-3 space-y-2">
                  {item.points.map((point) => (
                    <li key={point} className="flex gap-2 text-sm leading-relaxed text-slate-400">
                      <span className="mt-2 size-1 shrink-0 rounded-full bg-sky-400" />
                      <span>{point}</span>
                    </li>
                  ))}
                </ul>
              </article>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  )
}
