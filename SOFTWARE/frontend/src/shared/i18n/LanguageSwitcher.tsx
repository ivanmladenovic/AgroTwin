import { useTranslation } from 'react-i18next'

import { getAppLocale, setAppLocale, type AppLocale } from '@/shared/i18n/i18n'
import { cn } from '@/shared/lib/utils'

export function LanguageSwitcher({
  className,
  compact = false,
}: {
  className?: string
  compact?: boolean
}) {
  const { i18n } = useTranslation()
  const locale = getAppLocale()

  async function onChange(next: AppLocale) {
    if (next === locale) return
    await setAppLocale(next)
  }

  // Re-render when language changes.
  void i18n.language

  return (
    <div
      className={cn(
        'inline-flex items-center gap-0.5 rounded-md border border-white/15 bg-white/5 p-0.5',
        className,
      )}
      role="group"
      aria-label={locale === 'en' ? 'Language' : 'Jezik'}
    >
      <LangButton active={locale === 'sr'} onClick={() => void onChange('sr')} compact={compact}>
        SR
      </LangButton>
      <LangButton active={locale === 'en'} onClick={() => void onChange('en')} compact={compact}>
        EN
      </LangButton>
    </div>
  )
}

function LangButton({
  active,
  onClick,
  children,
  compact,
}: {
  active: boolean
  onClick: () => void
  children: string
  compact: boolean
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'rounded px-2 font-semibold uppercase tracking-wide transition-colors',
        compact ? 'h-7 text-[10px]' : 'h-8 text-xs',
        active
          ? 'bg-white/15 text-white'
          : 'text-sidebar-foreground/60 hover:bg-white/5 hover:text-white',
      )}
    >
      {children}
    </button>
  )
}
