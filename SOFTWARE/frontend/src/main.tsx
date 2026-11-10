import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { App } from '@/app/App'
import { getAppLocale } from '@/shared/i18n/i18n'
import '@/shared/i18n/i18n'
import './index.css'

const rootElement = document.getElementById('root')

if (!rootElement) {
  throw new Error('Root element not found')
}

document.documentElement.lang = getAppLocale() === 'en' ? 'en' : 'sr-Latn'

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
