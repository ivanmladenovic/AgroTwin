import { Reveal } from '@/components/ui/reveal'
import { SectionHeading } from '@/components/ui/section-heading'
import { CalendarClock, EyeOff, Unlink } from 'lucide-react'
import { useTranslation } from 'react-i18next'

export function ValueSection() {
  const { t } = useTranslation()

  const challenges = [
    {
      number: '01',
      title: t('value.items.visibility.title'),
      description: t('value.items.visibility.description'),
      icon: Unlink,
    },
    {
      number: '02',
      title: t('value.items.decisions.title'),
      description: t('value.items.decisions.description'),
      icon: EyeOff,
    },
    {
      number: '03',
      title: t('value.items.organization.title'),
      description: t('value.items.organization.description'),
      icon: CalendarClock,
    },
  ]

  return (
    <section id="platform" className="section-y relative">
      <div className="ambient-glow opacity-70" aria-hidden="true" />
      <div className="section-shell relative">
        <Reveal>
          <SectionHeading
            kicker={t('value.kicker')}
            title={t('value.title')}
            subtitle={t('value.subtitle')}
          />
        </Reveal>

        <div className="mt-12 grid gap-4 sm:mt-14 md:grid-cols-3 md:gap-5">
          {challenges.map((item, index) => (
            <Reveal key={item.number} delay={index * 90}>
              <article className="glass-card group h-full p-4 sm:p-6">
                <div className="mb-4 flex items-center gap-3 sm:mb-5 sm:gap-3.5">
                  <span className="flex size-11 items-center justify-center rounded-2xl bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/25 transition group-hover:bg-emerald-500/15 sm:size-12">
                    <item.icon className="size-5 sm:size-6" strokeWidth={2.1} aria-hidden />
                  </span>
                  <span className="font-mono text-xs font-semibold tracking-wide text-emerald-400/90">
                    {item.number}
                  </span>
                </div>
                <h3 className="text-xl font-bold text-white">{item.title}</h3>
                <p className="mt-3 text-sm leading-relaxed text-slate-400 sm:text-[15px]">
                  {item.description}
                </p>
              </article>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  )
}
