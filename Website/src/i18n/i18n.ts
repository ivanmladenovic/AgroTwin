import i18n from 'i18next'
import LanguageDetector from 'i18next-browser-languagedetector'
import { initReactI18next } from 'react-i18next'

import en from '@/i18n/locales/en.json'
import sr from '@/i18n/locales/sr.json'

export const SUPPORTED_LOCALES = ['sr', 'en'] as const
export type AppLocale = (typeof SUPPORTED_LOCALES)[number]

/** Same persistence key as the AgroTwin application. */
export const LOCALE_STORAGE_KEY = 'agrotwin.locale'

export const LOCALE_TO_BCP47: Record<AppLocale, string> = {
  sr: 'sr-Latn-RS',
  en: 'en',
}

void i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      sr: { translation: sr },
      en: { translation: en },
    },
    lng: 'sr',
    fallbackLng: 'sr',
    supportedLngs: [...SUPPORTED_LOCALES],
    nonExplicitSupportedLngs: true,
    interpolation: { escapeValue: false },
    returnNull: false,
    returnEmptyString: false,
    // Marketing site is Serbian-first. Only honor an explicit user choice in localStorage —
    // do not auto-switch to English from the browser language.
    detection: {
      order: ['localStorage'],
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

export async function setAppLocale(locale: AppLocale): Promise<void> {
  localStorage.setItem(LOCALE_STORAGE_KEY, locale)
  await i18n.changeLanguage(locale)
  document.documentElement.lang = LOCALE_TO_BCP47[locale]
}

export default i18n
