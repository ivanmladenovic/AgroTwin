import { cn } from '@/lib/utils'
import type { ReactNode } from 'react'

export function SectionHeading({
  kicker,
  title,
  subtitle,
  align = 'center',
  className,
  light = false,
  kickerTone = 'green',
}: {
  kicker?: string
  title: ReactNode
  subtitle?: ReactNode
  align?: 'left' | 'center'
  className?: string
  /** Kept for compatibility — page is dark-first. */
  light?: boolean
  kickerTone?: 'green' | 'blue'
}) {
  void light

  return (
    <div
      className={cn(
        'max-w-3xl',
        align === 'center' ? 'mx-auto text-center' : 'text-left',
        className,
      )}
    >
      {kicker ? (
        <p
          className={cn(
            'kicker mb-4',
            align === 'center' && 'mx-auto',
            kickerTone === 'blue' && 'kicker-blue',
          )}
        >
          {kicker}
        </p>
      ) : null}
      <h2 className="text-[1.65rem] font-bold leading-tight tracking-tight text-white sm:text-3xl md:text-4xl">
        {title}
      </h2>
      {subtitle ? (
        <p className="mt-3 text-[15px] leading-relaxed text-slate-400 sm:mt-4 sm:text-base md:text-lg">
          {subtitle}
        </p>
      ) : null}
    </div>
  )
}
