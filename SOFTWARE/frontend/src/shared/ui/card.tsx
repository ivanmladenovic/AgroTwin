import type { HTMLAttributes } from 'react'

import { cn } from '@/shared/lib/utils'

function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('rounded-xl border border-border bg-card', className)} {...props} />
}

function CardHeader({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('border-b border-border px-5 py-4', className)} {...props} />
}

function CardTitle({ className, ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return <h2 className={cn('kicker', className)} {...props} />
}

function CardContent({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('px-5 py-4', className)} {...props} />
}

export { Card, CardContent, CardHeader, CardTitle }
