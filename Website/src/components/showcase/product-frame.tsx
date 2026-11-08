import { cn } from '@/lib/utils'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

type ProductFrameProps = {
  title: string
  label?: string
  children: ReactNode
  className?: string
  large?: boolean
}

/** Browser-style product frame used across showcases. */
export function ProductFrame({
  title,
  label,
  children,
  className,
  large = false,
}: ProductFrameProps) {
  const { t } = useTranslation()

  return (
    <figure className={cn('relative', className)}>
      {label ? (
        <figcaption className="mb-2.5 flex flex-wrap items-center gap-2 sm:mb-3">
          <span className="kicker">{label}</span>
          <span className="text-[10px] text-slate-500 sm:text-[11px]">
            {t('features.illustrative')}
          </span>
        </figcaption>
      ) : null}

      <div
        className={cn(
          'overflow-hidden rounded-xl border border-emerald-500/30 bg-slate-950 sm:rounded-2xl',
          'shadow-[0_0_50px_-10px_rgba(16,185,129,0.25),0_24px_60px_-28px_rgba(0,0,0,0.7)]',
          'ring-1 ring-white/5',
        )}
      >
        <div className="flex items-center gap-2 border-b border-slate-800/90 bg-slate-900/90 px-2.5 py-2 sm:px-4 sm:py-2.5">
          <div className="flex shrink-0 items-center gap-1.5" aria-hidden>
            <span className="size-2 rounded-full bg-[#f87171]/80 sm:size-2.5" />
            <span className="size-2 rounded-full bg-[#fbbf24]/80 sm:size-2.5" />
            <span className="size-2 rounded-full bg-[#34d399]/80 sm:size-2.5" />
          </div>
          <div className="ml-1 flex min-w-0 flex-1 items-center justify-center sm:ml-2">
            <div
              className={cn(
                'w-full truncate rounded-md border border-slate-700/80 bg-slate-950/80 px-2 py-1 text-center text-[10px] font-medium text-slate-400 sm:px-3 sm:text-[11px]',
                large ? 'max-w-[16rem] sm:max-w-[22rem]' : 'max-w-[12rem] sm:max-w-[18rem]',
              )}
            >
              app.myagrotwin.com · {title}
            </div>
          </div>
          <div className="hidden w-10 sm:block" aria-hidden />
        </div>
        <div className="max-w-full overflow-hidden bg-slate-950">{children}</div>
      </div>
    </figure>
  )
}

export function FloatingLabel({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <div
      className={cn(
        'rounded-xl border border-slate-700/80 bg-slate-900/90 px-3 py-2 text-[11px] font-semibold text-white shadow-[0_12px_30px_-16px_rgba(16,185,129,0.35)] backdrop-blur-sm',
        className,
      )}
    >
      {children}
    </div>
  )
}
