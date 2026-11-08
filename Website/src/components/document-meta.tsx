import { getAppLocale, LOCALE_TO_BCP47 } from '@/i18n/i18n'
import { CONTACT_EMAIL, SITE_URL } from '@/lib/config'
import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'

function setMeta(attr: 'name' | 'property', key: string, content: string) {
  let node = document.head.querySelector(`meta[${attr}="${key}"]`) as HTMLMetaElement | null
  if (!node) {
    node = document.createElement('meta')
    node.setAttribute(attr, key)
    document.head.appendChild(node)
  }
  node.setAttribute('content', content)
}

function setLink(rel: string, href: string, attributes?: Record<string, string>) {
  const selector = attributes?.hreflang
    ? `link[rel="${rel}"][hreflang="${attributes.hreflang}"]`
    : `link[rel="${rel}"]:not([hreflang])`
  let node = document.head.querySelector(selector) as HTMLLinkElement | null
  if (!node) {
    node = document.createElement('link')
    node.setAttribute('rel', rel)
    if (attributes) {
      for (const [key, value] of Object.entries(attributes)) {
        node.setAttribute(key, value)
      }
    }
    document.head.appendChild(node)
  }
  node.setAttribute('href', href)
}

function upsertJsonLd(id: string, data: Record<string, unknown>) {
  let node = document.getElementById(id) as HTMLScriptElement | null
  if (!node) {
    node = document.createElement('script')
    node.type = 'application/ld+json'
    node.id = id
    document.head.appendChild(node)
  }
  node.textContent = JSON.stringify(data)
}

/** Keeps title, language, Open Graph and structured data in sync with the active locale. */
export function DocumentMeta() {
  const { t, i18n } = useTranslation()
  const locale = getAppLocale()
  void i18n.language

  useEffect(() => {
    const title = t('meta.title')
    const description = t('meta.description')
    const ogTitle = t('meta.ogTitle')
    const ogDescription = t('meta.ogDescription')
    const imagePath = '/assets/orchard-dashboard-hero.jpg'
    const absoluteImage = `${SITE_URL}${imagePath}`
    const pageUrl = `${SITE_URL}/`

    document.title = title
    document.documentElement.lang = LOCALE_TO_BCP47[locale]

    setMeta('name', 'description', description)
    setMeta('name', 'keywords', t('meta.keywords'))
    setMeta('property', 'og:type', 'website')
    setMeta('property', 'og:site_name', 'AgroTwin')
    setMeta('property', 'og:url', pageUrl)
    setMeta('property', 'og:title', ogTitle)
    setMeta('property', 'og:description', ogDescription)
    setMeta('property', 'og:image', absoluteImage)
    setMeta('property', 'og:locale', locale === 'en' ? 'en_US' : 'sr_RS')
    setMeta('property', 'og:locale:alternate', locale === 'en' ? 'sr_RS' : 'en_US')
    setMeta('name', 'twitter:card', 'summary_large_image')
    setMeta('name', 'twitter:title', ogTitle)
    setMeta('name', 'twitter:description', ogDescription)
    setMeta('name', 'twitter:image', absoluteImage)

    setLink('canonical', pageUrl)
    setLink('alternate', pageUrl, { hreflang: 'sr-Latn' })
    setLink('alternate', pageUrl, { hreflang: 'en' })
    setLink('alternate', pageUrl, { hreflang: 'x-default' })

    upsertJsonLd('agrotwin-software-jsonld', {
      '@context': 'https://schema.org',
      '@type': 'SoftwareApplication',
      name: 'AgroTwin',
      applicationCategory: 'BusinessApplication',
      operatingSystem: 'Web',
      url: pageUrl,
      description,
      image: absoluteImage,
      offers: [
        {
          '@type': 'Offer',
          name: t('pricing.monthly'),
          price: '29.00',
          priceCurrency: 'EUR',
          category: 'Subscription',
          url: pageUrl,
        },
        {
          '@type': 'Offer',
          name: t('pricing.annual'),
          price: '299.00',
          priceCurrency: 'EUR',
          category: 'Subscription',
          url: pageUrl,
        },
      ],
      provider: {
        '@type': 'Organization',
        name: 'AgroTwin',
        url: pageUrl,
        email: CONTACT_EMAIL,
        logo: `${SITE_URL}/favicon.png`,
      },
    })

    upsertJsonLd('agrotwin-website-jsonld', {
      '@context': 'https://schema.org',
      '@type': 'WebSite',
      name: 'AgroTwin',
      url: pageUrl,
      inLanguage: [LOCALE_TO_BCP47.sr, LOCALE_TO_BCP47.en],
      description,
    })
  }, [locale, t])

  return null
}
