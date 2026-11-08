import { BrandLogo } from '@/components/ui/brand-logo'
import { CONTACT_EMAIL, CONTACT_PHONE, CONTACT_PHONE_TEL } from '@/lib/config'
import { useTranslation } from 'react-i18next'

const COPYRIGHT_YEAR = new Date().getFullYear()

export function Footer() {
  const { t } = useTranslation()

  const platformLinks = [
    { href: '#platform', label: t('nav.platform') },
    { href: '#features', label: t('nav.features') },
    { href: '#digital-twin', label: t('footer.digitalTwin') },
    { href: '#satellite', label: t('footer.satellite') },
    { href: '#ai-agronomist', label: t('footer.agronomist') },
  ]

  const companyLinks = [
    { href: '#pricing', label: t('nav.pricing') },
    { href: '#enterprise', label: t('nav.enterprise') },
    { href: '#enterprise-contact', label: t('footer.enterpriseContact') },
    { href: '#faq', label: t('nav.faq') },
  ]

  return (
    <footer className="border-t border-slate-800/80 bg-[#05070c]">
      <div className="section-shell grid gap-6 py-8 sm:gap-8 sm:py-10 md:grid-cols-[1.2fr_1fr_1fr]">
        <div className="md:col-span-1">
          <BrandLogo variant="nav" className="h-8 w-auto object-contain object-left sm:h-9" />
          <div className="mt-3 flex flex-col gap-1 text-sm">
            <a
              href={`mailto:${CONTACT_EMAIL}`}
              className="inline-block break-all font-medium text-emerald-400 hover:text-emerald-300 hover:underline"
            >
              {CONTACT_EMAIL}
            </a>
            <a
              href={`tel:${CONTACT_PHONE_TEL}`}
              className="inline-block font-medium text-emerald-400 hover:text-emerald-300 hover:underline"
            >
              {CONTACT_PHONE}
            </a>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-6 md:contents">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-500">
              {t('footer.platform')}
            </p>
            <ul className="mt-2.5 space-y-1.5">
              {platformLinks.map((link) => (
                <li key={link.href}>
                  <a href={link.href} className="text-sm text-slate-300 hover:text-emerald-400">
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-500">
              {t('footer.company')}
            </p>
            <ul className="mt-2.5 space-y-1.5">
              {companyLinks.map((link) => (
                <li key={link.href}>
                  <a href={link.href} className="text-sm text-slate-300 hover:text-emerald-400">
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      <div className="border-t border-slate-800/80">
        <div className="section-shell py-3 text-xs text-slate-500">
          <p>{t('footer.rights', { year: COPYRIGHT_YEAR })}</p>
        </div>
      </div>
    </footer>
  )
}
