import { getAppLocale, setAppLocale, type AppLocale } from '@/i18n/i18n'
import { cn } from '@/lib/utils'
import { useTranslation } from 'react-i18next'

export function LanguageSwitcher({
  className,
  tone = 'default',
}: {
  className?: string
  tone?: 'default' | 'onDark'
}) {
  const { i18n, t } = useTranslation()
  const locale = getAppLocale()
  void i18n.language
  void tone

  async function onChange(next: AppLocale) {
    if (next === locale) return
    await setAppLocale(next)
  }

  return (
    <div
      className={cn(
        'inline-flex items-center gap-0.5 rounded-lg border border-slate-700/80 bg-slate-900/70 p-0.5 backdrop-blur-sm',
        className,
      )}
      role="group"
      aria-label={t('a11y.language')}
    >
      <LangButton active={locale === 'sr'} onClick={() => void onChange('sr')}>
        SR
      </LangButton>
      <LangButton active={locale === 'en'} onClick={() => void onChange('en')}>
        EN
      </LangButton>
    </div>
  )
}

function LangButton({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: string
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'h-8 rounded-md px-2.5 text-[11px] font-bold uppercase tracking-wide transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background',
        active
          ? 'bg-emerald-500 text-slate-950'
          : 'text-slate-400 hover:bg-white/5 hover:text-white',
      )}
      aria-pressed={active}
    >
      {children}
    </button>
  )
}
