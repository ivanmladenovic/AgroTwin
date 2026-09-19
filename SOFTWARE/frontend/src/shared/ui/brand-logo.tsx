import type { ImgHTMLAttributes } from 'react'

import logo from '@/assets/agrotwin-logo.png'
import mark from '@/assets/agrotwin-mark.png'
import { cn } from '@/shared/lib/utils'

type BrandLogoProps = Omit<ImgHTMLAttributes<HTMLImageElement>, 'src' | 'alt'> & {
  variant?: 'full' | 'mark'
}

export function BrandLogo({ variant = 'full', className, ...props }: BrandLogoProps) {
  return (
    <img
      src={variant === 'mark' ? mark : logo}
      alt="AgroTwin"
      className={cn('select-none', className)}
      {...props}
    />
  )
}
