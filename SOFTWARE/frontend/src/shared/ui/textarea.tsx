import type { TextareaHTMLAttributes } from 'react'

import { cn } from '@/shared/lib/utils'

function Textarea({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={cn(
        'flex min-h-24 w-full rounded-lg border border-border bg-card px-3 py-2 text-base text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 lg:text-sm',
        className,
      )}
      {...props}
    />
  )
}

export { Textarea }
