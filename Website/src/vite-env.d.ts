/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_APP_URL?: string
  readonly VITE_SITE_URL?: string
  readonly VITE_CONTACT_EMAIL?: string
  readonly VITE_CONTACT_PHONE?: string
  readonly VITE_ENTERPRISE_CONTACT_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
