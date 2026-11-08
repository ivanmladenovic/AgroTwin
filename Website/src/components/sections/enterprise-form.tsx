import { Button } from '@/components/ui/button'
import {
  CONTACT_EMAIL,
  ENTERPRISE_CONTACT_URL,
  HAS_ENTERPRISE_API,
} from '@/lib/config'
import { cn } from '@/lib/utils'
import { useState, type FormEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

type FormState = {
  fullName: string
  company: string
  businessEmail: string
  country: string
  organizationType: string
  farmCount: string
  message: string
}

const initialState: FormState = {
  fullName: '',
  company: '',
  businessEmail: '',
  country: '',
  organizationType: '',
  farmCount: '',
  message: '',
}

const ORG_KEYS = [
  'producer',
  'manufacturer',
  'cooperative',
  'buyer',
  'organization',
  'other',
] as const

export function EnterpriseForm() {
  const { t } = useTranslation()
  const [values, setValues] = useState<FormState>(initialState)
  const [errors, setErrors] = useState<Partial<Record<keyof FormState, string>>>({})
  const [status, setStatus] = useState<'idle' | 'submitting' | 'success' | 'error' | 'mailto'>(
    'idle',
  )
  const [message, setMessage] = useState('')

  function validate(next: FormState) {
    const result: Partial<Record<keyof FormState, string>> = {}
    if (!next.fullName.trim()) result.fullName = t('form.errors.fullName')
    if (!next.company.trim()) result.company = t('form.errors.company')
    if (!next.businessEmail.trim()) result.businessEmail = t('form.errors.email')
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(next.businessEmail.trim())) {
      result.businessEmail = t('form.errors.emailInvalid')
    }
    if (!next.country.trim()) result.country = t('form.errors.country')
    if (!next.organizationType) result.organizationType = t('form.errors.orgType')
    if (next.message.trim().length < 20) result.message = t('form.errors.message')
    return result
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const nextErrors = validate(values)
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length > 0) {
      setStatus('idle')
      setMessage('')
      const firstKey = Object.keys(nextErrors)[0]
      if (firstKey) document.getElementById(firstKey)?.focus()
      return
    }

    setStatus('submitting')
    setMessage('')

    const orgLabel = t(`form.orgTypes.${values.organizationType}`)

    if (HAS_ENTERPRISE_API && ENTERPRISE_CONTACT_URL) {
      try {
        const response = await fetch(ENTERPRISE_CONTACT_URL, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            full_name: values.fullName.trim(),
            company: values.company.trim(),
            business_email: values.businessEmail.trim(),
            country: values.country.trim(),
            organization_type: orgLabel,
            farm_count: values.farmCount.trim() || null,
            message: values.message.trim(),
            source: 'agrotwin-marketing-website',
          }),
        })

        if (!response.ok) throw new Error(`Request failed with status ${response.status}`)

        setStatus('success')
        setMessage(t('form.success'))
        setValues(initialState)
        return
      } catch {
        setStatus('error')
        setMessage(t('form.error'))
        return
      }
    }

    const subject = encodeURIComponent(`AgroTwin Enterprise — ${values.company.trim()}`)
    const body = encodeURIComponent(
      [
        `Full name: ${values.fullName.trim()}`,
        `Company: ${values.company.trim()}`,
        `Business email: ${values.businessEmail.trim()}`,
        `Country: ${values.country.trim()}`,
        `Organization type: ${orgLabel}`,
        `Farms / producers: ${values.farmCount.trim() || '—'}`,
        '',
        'Message:',
        values.message.trim(),
      ].join('\n'),
    )

    window.location.href = `mailto:${CONTACT_EMAIL}?subject=${subject}&body=${body}`
    setStatus('mailto')
    setMessage(t('form.mailtoNote', { email: CONTACT_EMAIL }))
  }

  return (
    <form
      id="enterprise-contact"
      onSubmit={onSubmit}
      className="rounded-2xl border border-white/10 bg-white/[0.04] p-5 sm:p-6"
      noValidate
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t('form.fullName')} error={errors.fullName} htmlFor="fullName">
          <input
            id="fullName"
            name="fullName"
            autoComplete="name"
            value={values.fullName}
            aria-invalid={Boolean(errors.fullName) || undefined}
            aria-describedby={errors.fullName ? 'fullName-error' : undefined}
            onChange={(e) => setValues((v) => ({ ...v, fullName: e.target.value }))}
            className={fieldClass(errors.fullName)}
          />
        </Field>
        <Field label={t('form.company')} error={errors.company} htmlFor="company">
          <input
            id="company"
            name="company"
            autoComplete="organization"
            value={values.company}
            aria-invalid={Boolean(errors.company) || undefined}
            aria-describedby={errors.company ? 'company-error' : undefined}
            onChange={(e) => setValues((v) => ({ ...v, company: e.target.value }))}
            className={fieldClass(errors.company)}
          />
        </Field>
        <Field label={t('form.email')} error={errors.businessEmail} htmlFor="businessEmail">
          <input
            id="businessEmail"
            name="businessEmail"
            type="email"
            autoComplete="email"
            value={values.businessEmail}
            aria-invalid={Boolean(errors.businessEmail) || undefined}
            aria-describedby={errors.businessEmail ? 'businessEmail-error' : undefined}
            onChange={(e) => setValues((v) => ({ ...v, businessEmail: e.target.value }))}
            className={fieldClass(errors.businessEmail)}
          />
        </Field>
        <Field label={t('form.country')} error={errors.country} htmlFor="country">
          <input
            id="country"
            name="country"
            autoComplete="country-name"
            value={values.country}
            aria-invalid={Boolean(errors.country) || undefined}
            aria-describedby={errors.country ? 'country-error' : undefined}
            onChange={(e) => setValues((v) => ({ ...v, country: e.target.value }))}
            className={fieldClass(errors.country)}
          />
        </Field>
        <Field label={t('form.orgType')} error={errors.organizationType} htmlFor="organizationType">
          <select
            id="organizationType"
            name="organizationType"
            value={values.organizationType}
            aria-invalid={Boolean(errors.organizationType) || undefined}
            aria-describedby={errors.organizationType ? 'organizationType-error' : undefined}
            onChange={(e) => setValues((v) => ({ ...v, organizationType: e.target.value }))}
            className={fieldClass(errors.organizationType)}
          >
            <option value="">{t('form.orgSelect')}</option>
            {ORG_KEYS.map((key) => (
              <option key={key} value={key}>
                {t(`form.orgTypes.${key}`)}
              </option>
            ))}
          </select>
        </Field>
        <Field label={t('form.farms')} htmlFor="farmCount">
          <input
            id="farmCount"
            name="farmCount"
            inputMode="numeric"
            value={values.farmCount}
            onChange={(e) => setValues((v) => ({ ...v, farmCount: e.target.value }))}
            className={fieldClass()}
          />
        </Field>
      </div>

      <Field className="mt-4" label={t('form.message')} error={errors.message} htmlFor="message">
        <textarea
          id="message"
          name="message"
          rows={5}
          value={values.message}
          aria-invalid={Boolean(errors.message) || undefined}
          aria-describedby={errors.message ? 'message-error' : undefined}
          onChange={(e) => setValues((v) => ({ ...v, message: e.target.value }))}
          className={cn(fieldClass(errors.message), 'resize-y')}
          placeholder={t('form.messagePlaceholder')}
        />
      </Field>

      <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Button
          type="submit"
          variant="primary"
          className="bg-brand-twin text-sidebar hover:bg-[#27a4ae]"
          disabled={status === 'submitting'}
        >
          {status === 'submitting' ? t('form.submitting') : t('form.submit')}
        </Button>
        <p className="text-xs text-white/55">{t('enterprise.ctaSupport')}</p>
      </div>

      {message ? (
        <p
          role="status"
          className={cn(
            'mt-4 rounded-xl px-3 py-2.5 text-sm',
            status === 'success' && 'bg-emerald-500/15 text-emerald-100',
            status === 'error' && 'bg-red-500/15 text-red-100',
            status === 'mailto' && 'bg-white/10 text-white/85',
          )}
        >
          {message}
        </p>
      ) : null}

      {!HAS_ENTERPRISE_API ? (
        <p className="mt-3 text-[11px] leading-relaxed text-white/45">
          {t('form.integrationNote', { email: CONTACT_EMAIL })}
        </p>
      ) : null}
    </form>
  )
}

function Field({
  label,
  htmlFor,
  error,
  children,
  className,
}: {
  label: string
  htmlFor: string
  error?: string
  children: ReactNode
  className?: string
}) {
  return (
    <div className={cn('block', className)}>
      <label
        htmlFor={htmlFor}
        className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-white/70"
      >
        {label}
      </label>
      {children}
      {error ? (
        <span id={`${htmlFor}-error`} role="alert" className="mt-1.5 block text-xs text-red-200">
          {error}
        </span>
      ) : null}
    </div>
  )
}

function fieldClass(error?: string) {
  return cn(
    'w-full rounded-xl border bg-white/5 px-3.5 py-2.5 text-sm text-white outline-none transition placeholder:text-white/35 focus-visible:ring-2 focus-visible:ring-brand-twin/50',
    error ? 'border-red-300/50' : 'border-white/15 focus:border-brand-twin/60',
  )
}
