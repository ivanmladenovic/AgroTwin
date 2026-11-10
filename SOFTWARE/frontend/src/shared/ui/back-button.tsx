import type { ButtonHTMLAttributes, ReactNode } from 'react'
import type { To } from 'react-router-dom'

import { tr } from '@/shared/i18n/i18n'
import { useSmartBack } from '@/shared/lib/navigation'
import { cn } from '@/shared/lib/utils'
import { Button } from '@/shared/ui/button'

type BackButtonProps = {
  fallback?: To
  children?: ReactNode
  variant?: 'outline' | 'ghost' | 'default'
  size?: 'default' | 'sm' | 'lg'
  className?: string
} & Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'onClick' | 'type'>

export function BackButton({
  fallback = '/',
  children,
  variant = 'outline',
  size = 'sm',
  className,
  ...props
}: BackButtonProps) {
  const goBack = useSmartBack(fallback)

  return (
    <Button type="button" variant={variant} size={size} className={className} onClick={() => goBack()} {...props}>
      {children ?? tr('Nazad')}
    </Button>
  )
}

export function BackLink({
  fallback = '/',
  children,
  className,
}: {
  fallback?: To
  children?: ReactNode
  className?: string
}) {
  const goBack = useSmartBack(fallback)

  return (
    <button
      type="button"
      onClick={() => goBack()}
      className={cn('text-sm text-muted-foreground hover:text-foreground', className)}
    >
      {children ?? tr('Nazad')}
    </button>
  )
}
