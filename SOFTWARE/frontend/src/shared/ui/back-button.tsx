import type { ButtonHTMLAttributes, ReactNode } from 'react'
import type { To } from 'react-router-dom'

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
  children = 'Nazad',
  variant = 'outline',
  size = 'sm',
  className,
  ...props
}: BackButtonProps) {
  const goBack = useSmartBack(fallback)

  return (
    <Button type="button" variant={variant} size={size} className={className} onClick={() => goBack()} {...props}>
      {children}
    </Button>
  )
}

export function BackLink({
  fallback = '/',
  children = 'Nazad',
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
      {children}
    </button>
  )
}
