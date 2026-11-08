import { LanguageSwitcher } from '@/components/language-switcher'
import { BrandLogo } from '@/components/ui/brand-logo'
import { ButtonLink } from '@/components/ui/button'
import { APP_LOGIN_URL } from '@/lib/config'
import { cn } from '@/lib/utils'
import { Menu, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

export function Navbar() {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const [scrolled, setScrolled] = useState(false)

  const links = [
    { href: '#platform', label: t('nav.platform') },
    { href: '#features', label: t('nav.features') },
    { href: '#pricing', label: t('nav.pricing') },
    { href: '#enterprise', label: t('nav.enterprise') },
    { href: '#faq', label: t('nav.faq') },
  ]

  const solid = scrolled || open

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 18)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  useEffect(() => {
    document.body.style.overflow = open ? 'hidden' : ''
    return () => {
      document.body.style.overflow = ''
    }
  }, [open])

  useEffect(() => {
    const onResize = () => {
      if (window.matchMedia('(min-width: 1024px)').matches) setOpen(false)
    }
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  return (
    <header
      className={cn(
        'fixed inset-x-0 top-0 z-50 border-b transition-colors duration-300',
        solid
          ? 'border-slate-800/80 bg-[#07080b]/85 backdrop-blur-xl'
          : 'border-transparent bg-gradient-to-b from-[#07080b]/80 via-[#07080b]/35 to-transparent',
      )}
    >
      <div className="section-shell flex h-14 items-center justify-between gap-2 sm:h-16 lg:h-[4.25rem]">
        <a href="#top" className="min-w-0 shrink" aria-label={t('a11y.home')}>
          <BrandLogo
            variant="nav"
            className="h-8 w-auto max-w-[11.5rem] object-contain object-left drop-shadow-[0_0_12px_rgba(16,185,129,0.25)] sm:h-9 sm:max-w-none lg:h-10"
          />
        </a>

        <nav className="hidden items-center gap-1 lg:flex" aria-label={t('a11y.primaryNav')}>
          {links.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="rounded-lg px-3 py-2 text-sm font-semibold text-slate-300 transition hover:bg-white/5 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            >
              {link.label}
            </a>
          ))}
        </nav>

        <div className="hidden items-center gap-2 lg:flex">
          <LanguageSwitcher tone="onDark" />
          <ButtonLink href={APP_LOGIN_URL} className="px-4 py-2.5">
            {t('nav.getStarted')}
          </ButtonLink>
        </div>

        <div className="flex shrink-0 items-center lg:hidden">
          <button
            type="button"
            className="inline-flex size-10 items-center justify-center rounded-xl border border-slate-700/80 bg-slate-900/70 text-white backdrop-blur-sm transition hover:border-emerald-500/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            aria-expanded={open}
            aria-controls="mobile-nav"
            aria-label={open ? t('a11y.closeMenu') : t('a11y.openMenu')}
            onClick={() => setOpen((value) => !value)}
          >
            {open ? <X className="size-5" /> : <Menu className="size-5" />}
          </button>
        </div>
      </div>

      <div
        id="mobile-nav"
        className={cn(
          'border-t border-slate-800 bg-[#07080b]/95 backdrop-blur-xl lg:hidden',
          open ? 'block' : 'hidden',
        )}
      >
        <nav
          className="section-shell flex max-h-[min(28rem,calc(100dvh-3.5rem))] flex-col gap-1 overflow-y-auto overscroll-contain py-3 pb-[max(1rem,env(safe-area-inset-bottom))] sm:max-h-[calc(100dvh-4rem)] sm:py-4"
          aria-label={t('a11y.mobileNav')}
        >
          {links.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="rounded-xl px-3 py-3.5 text-base font-medium text-slate-200 hover:bg-white/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
              onClick={() => setOpen(false)}
            >
              {link.label}
            </a>
          ))}
          <div className="mt-2 flex items-center justify-between gap-3 border-t border-slate-800 pt-3">
            <LanguageSwitcher tone="onDark" />
            <ButtonLink href={APP_LOGIN_URL} className="flex-1" onClick={() => setOpen(false)}>
              {t('nav.getStarted')}
            </ButtonLink>
          </div>
        </nav>
      </div>
    </header>
  )
}
