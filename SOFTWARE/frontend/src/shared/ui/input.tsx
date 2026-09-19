import type { InputHTMLAttributes } from 'react'

import { cn } from '@/shared/lib/utils'

function Input({ className, type = 'text', ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      type={type}
      className={cn(
        'flex h-11 w-full rounded-lg border border-border bg-card px-3 py-2 text-base text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 lg:h-10 lg:text-sm',
        className,
      )}
      {...props}
    />
  )
}

export { Input }
