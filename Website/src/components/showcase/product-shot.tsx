import { ProductFrame } from '@/components/showcase/product-frame'
import { cn } from '@/lib/utils'

type ProductShotProps = {
  title: string
  label?: string
  webp: string
  jpg: string
  alt: string
  className?: string
  imageClassName?: string
  portrait?: boolean
}

/** Framed product screenshot from AgroTwin presentation / product UI. */
export function ProductShot({
  title,
  label,
  webp,
  jpg,
  alt,
  className,
  imageClassName,
  portrait = false,
}: ProductShotProps) {
  return (
    <ProductFrame title={title} label={label} className={className} large>
      <div className={cn('bg-slate-950', portrait && 'flex justify-center p-4 sm:p-6')}>
        <picture>
          <source srcSet={webp} type="image/webp" />
          <img
            src={jpg}
            alt={alt}
            loading="lazy"
            decoding="async"
            className={cn(
              'h-auto max-w-full',
              portrait
                ? 'mx-auto max-h-[280px] w-auto rounded-lg shadow-sm sm:max-h-[420px] sm:rounded-xl md:max-h-[480px]'
                : 'block w-full',
              imageClassName,
            )}
          />
        </picture>
      </div>
    </ProductFrame>
  )
}
