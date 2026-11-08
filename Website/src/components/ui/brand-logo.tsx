import logo from '@/assets/agrotwin-logo.webp'
import logoNav from '@/assets/agrotwin-logo-nav.webp'
import mark from '@/assets/agrotwin-mark.webp'
import { cn } from '@/lib/utils'
import type { ImgHTMLAttributes } from 'react'

type BrandLogoProps = Omit<ImgHTMLAttributes<HTMLImageElement>, 'src' | 'alt'> & {
  variant?: 'full' | 'mark' | 'nav'
}

export function BrandLogo({ variant = 'full', className, ...props }: BrandLogoProps) {
  const src = variant === 'mark' ? mark : variant === 'nav' ? logoNav : logo
  const width = variant === 'mark' ? 128 : variant === 'nav' ? 350 : 360
  const height = variant === 'mark' ? 128 : variant === 'nav' ? 104 : 360

  return (
    <img
      src={src}
      alt="AgroTwin"
      width={width}
      height={height}
      decoding="async"
      className={cn('select-none', className)}
      {...props}
    />
  )
}
