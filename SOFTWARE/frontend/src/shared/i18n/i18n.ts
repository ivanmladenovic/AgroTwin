import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import LanguageDetector from 'i18next-browser-languagedetector'

import en from '@/shared/i18n/locales/en/translation.json'
import sr from '@/shared/i18n/locales/sr/translation.json'

export const SUPPORTED_LOCALES = ['sr', 'en'] as const
export type AppLocale = (typeof SUPPORTED_LOCALES)[number]

export const LOCALE_STORAGE_KEY = 'agrotwin.locale'

export const LOCALE_TO_BCP47: Record<AppLocale, string> = {
  sr: 'sr-Latn-RS',
  en: 'en-GB',
}

const resources = {
  sr: { translation: sr },
  en: { translation: en },
}

void i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    fallbackLng: 'sr',
    supportedLngs: [...SUPPORTED_LOCALES],
    nonExplicitSupportedLngs: true,
    interpolation: { escapeValue: false },
    returnNull: false,
    returnEmptyString: false,
    keySeparator: false,
    nsSeparator: false,
    detection: {
      order: ['localStorage', 'navigator'],
      lookupLocalStorage: LOCALE_STORAGE_KEY,
      caches: ['localStorage'],
    },
  })

export function normalizeLocale(value: string | null | undefined): AppLocale {
  if (!value) return 'sr'
  const lower = value.toLowerCase()
  if (lower.startsWith('en')) return 'en'
  if (lower.startsWith('sr')) return 'sr'
  return 'sr'
}

export function getAppLocale(): AppLocale {
  return normalizeLocale(i18n.resolvedLanguage || i18n.language)
}

export function getBcp47Locale(locale: AppLocale = getAppLocale()): string {
  return LOCALE_TO_BCP47[locale]
}

/** Translate using Serbian natural keys. Missing EN keys fall back to the Serbian source. */
export function tr(key: string, options?: Record<string, unknown>): string {
  if (!key) return key
  return i18n.t(key, { defaultValue: key, ...(options ?? {}) })
}

export async function setAppLocale(locale: AppLocale): Promise<void> {
  localStorage.setItem(LOCALE_STORAGE_KEY, locale)
  await i18n.changeLanguage(locale)
  document.documentElement.lang = locale === 'en' ? 'en' : 'sr-Latn'
}

export default i18n
