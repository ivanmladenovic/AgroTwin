import { Reveal } from '@/components/ui/reveal'
import { SectionHeading } from '@/components/ui/section-heading'
import { cn } from '@/lib/utils'
import { ChevronDown } from 'lucide-react'
import { useId, useState } from 'react'
import { useTranslation } from 'react-i18next'

type FaqItemData = { q: string; a: string }

export function FaqSection() {
  const { t } = useTranslation()
  const faqs = t('faq.items', { returnObjects: true }) as FaqItemData[]
  const [openIndex, setOpenIndex] = useState<number | null>(0)

  return (
    <section id="faq" className="section-y relative border-t border-slate-800/70">
      <div className="section-shell relative">
        <Reveal>
          <SectionHeading kicker={t('faq.kicker')} title={t('faq.title')} />
        </Reveal>

        <div className="mx-auto mt-12 max-w-3xl space-y-3 sm:mt-14">
          {faqs.map((item, index) => (
            <Reveal key={item.q} delay={index * 30}>
              <FaqItem
                question={item.q}
                answer={item.a}
                open={openIndex === index}
                onToggle={() => setOpenIndex((current) => (current === index ? null : index))}
              />
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  )
}

function FaqItem({
  question,
  answer,
  open,
  onToggle,
}: {
  question: string
  answer: string
  open: boolean
  onToggle: () => void
}) {
  const panelId = useId()
  const buttonId = useId()

  return (
    <div
      className={cn(
        'rounded-2xl border bg-slate-900/50 backdrop-blur-xl transition-colors duration-300',
        open ? 'border-emerald-500/35' : 'border-slate-800/80 hover:border-slate-700',
      )}
    >
      <h3>
        <button
          id={buttonId}
          type="button"
          className="flex w-full items-start justify-between gap-3 px-4 py-4 text-left text-sm font-semibold text-white sm:items-center sm:gap-4 sm:px-5 sm:text-base"
          aria-expanded={open}
          aria-controls={panelId}
          onClick={onToggle}
        >
          <span>{question}</span>
          <ChevronDown
            className={cn(
              'size-5 shrink-0 text-slate-500 transition-transform duration-200',
              open && 'rotate-180 text-emerald-400',
            )}
            aria-hidden
          />
        </button>
      </h3>
      <div
        id={panelId}
        role="region"
        aria-labelledby={buttonId}
        className={cn(
          'grid transition-[grid-template-rows] duration-200',
          open ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]',
        )}
      >
        <div className="overflow-hidden">
          <p className="px-4 pb-4 text-sm leading-relaxed text-slate-400 sm:px-5 sm:pb-5">
            {answer}
          </p>
        </div>
      </div>
    </div>
  )
}
