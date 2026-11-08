import { cn } from '@/lib/utils'
import type { AnchorHTMLAttributes, ButtonHTMLAttributes, ReactNode } from 'react'

type Variant = 'primary' | 'secondary' | 'ghost' | 'outline' | 'enterprise'

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant
  asChild?: boolean
  children: ReactNode
}

const variants: Record<Variant, string> = {
  primary:
    'bg-gradient-to-b from-emerald-400 to-emerald-600 text-primary-foreground shadow-[0_0_28px_-8px_rgba(16,185,129,0.65)] hover:from-emerald-300 hover:to-emerald-500',
  secondary:
    'bg-slate-900/70 text-foreground border border-slate-700/80 hover:border-emerald-500/40 hover:bg-slate-800/80',
  ghost: 'bg-transparent text-foreground hover:bg-white/5',
  outline:
    'border border-slate-600/80 bg-transparent text-white hover:border-emerald-400/50 hover:bg-emerald-500/10',
  enterprise:
    'bg-white text-slate-950 hover:bg-slate-100 shadow-[0_0_30px_-10px_rgba(255,255,255,0.35)]',
}

const base =
  'inline-flex items-center justify-center gap-2 rounded-xl px-5 py-3 text-sm font-semibold transition-all duration-200 hover:scale-[1.02] active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-55'

export function Button({
  className,
  variant = 'primary',
  children,
  type = 'button',
  ...props
}: ButtonProps) {
  return (
    <button type={type} className={cn(base, variants[variant], className)} {...props}>
      {children}
    </button>
  )
}

export function ButtonLink({
  className,
  variant = 'primary',
  href,
  children,
  ...props
}: {
  href: string
  variant?: Variant
  className?: string
  children: ReactNode
} & AnchorHTMLAttributes<HTMLAnchorElement>) {
  return (
    <a href={href} className={cn(base, variants[variant], className)} {...props}>
      {children}
    </a>
  )
}
