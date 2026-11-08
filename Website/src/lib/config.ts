const trimSlash = (value: string) => value.replace(/\/$/, '')

export const APP_URL = trimSlash(
  (import.meta.env.VITE_APP_URL as string | undefined)?.trim() ||
    'https://app.myagrotwin.com',
)

export const APP_LOGIN_URL = `${APP_URL}/login`

export const CONTACT_EMAIL =
  (import.meta.env.VITE_CONTACT_EMAIL as string | undefined)?.trim() ||
  'contact@myagrotwin.com'

export const CONTACT_MAILTO = `mailto:${CONTACT_EMAIL}`

export const licenseMailto = (plan: 'monthly' | 'annual') => {
  const subject =
    plan === 'monthly'
      ? 'AgroTwin — zahtev za mesečnu licencu'
      : 'AgroTwin — zahtev za godišnju licencu'
  return `${CONTACT_MAILTO}?subject=${encodeURIComponent(subject)}`
}

export const ENTERPRISE_MAILTO = `${CONTACT_MAILTO}?subject=${encodeURIComponent(
  'AgroTwin — upit za preduzeća',
)}`

export const CONTACT_PHONE =
  (import.meta.env.VITE_CONTACT_PHONE as string | undefined)?.trim() ||
  '+381 61 1843255'

export const CONTACT_PHONE_TEL = CONTACT_PHONE.replace(/\s+/g, '')

/** Marketing site origin for canonical / Open Graph absolute URLs. */
export const SITE_URL = trimSlash(
  (import.meta.env.VITE_SITE_URL as string | undefined)?.trim() ||
    'https://myagrotwin.com',
)

/** Optional backend endpoint for enterprise inquiries. */
export const ENTERPRISE_CONTACT_URL = (
  import.meta.env.VITE_ENTERPRISE_CONTACT_URL as string | undefined
)?.trim()

export const HAS_ENTERPRISE_API = Boolean(ENTERPRISE_CONTACT_URL)

export const MONTHLY_PRICE = '€29'
export const ANNUAL_PRICE = '€299'
export const ANNUAL_SAVINGS = '€49'
