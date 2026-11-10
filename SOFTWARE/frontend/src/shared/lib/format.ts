import { getBcp47Locale, tr } from '@/shared/i18n/i18n'

/** @deprecated Prefer getBcp47Locale() — kept for call sites that import LOCALE. */
export const LOCALE = 'sr-Latn-RS'

function activeLocale() {
  return getBcp47Locale()
}

export function formatNumber(value: number | string | null | undefined) {
  if (value == null || value === '') return '—'
  const numeric = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(numeric)) return String(value)
  return numeric.toLocaleString(activeLocale())
}

export function isEurUnit(unit: string | null | undefined) {
  const value = (unit ?? '').trim().toUpperCase().replace('€', 'EUR')
  return value === 'EUR' || value === 'EURO'
}

export function formatLineItem(item: {
  name?: string | null
  quantity: string | number | null
  unit: string | null
  volume?: string | number | null
  volume_unit?: string | null
  amount?: string | number | null
}) {
  const parts: string[] = []
  if (item.name?.trim()) parts.push(item.name.trim())
  if (!isEurUnit(item.unit) && item.quantity != null && item.quantity !== '') {
    parts.push(`${formatQuantity(item.quantity)} ${item.unit ?? ''}`.trim())
  }
  if (item.volume != null && item.volume !== '') {
    parts.push(`${tr('Litraža')} ${formatQuantity(item.volume)} ${item.volume_unit || 'L'}`.trim())
  }
  if (item.amount != null && item.amount !== '') {
    parts.push(formatMoney(item.amount, 'EUR'))
  } else if (isEurUnit(item.unit) && item.quantity != null && item.quantity !== '') {
    parts.push(formatMoney(item.quantity, 'EUR'))
  }
  return parts.join(' · ') || '—'
}

function formatQuantity(value: string | number) {
  const numeric = typeof value === 'number' ? value : Number(value)
  if (Number.isNaN(numeric)) return String(value)
  return numeric.toLocaleString(activeLocale(), { maximumFractionDigits: 3 })
}

export function formatWorkQuantities(
  items: Array<{
    name?: string | null
    quantity: string | number | null
    unit: string | null
    volume?: string | number | null
    volume_unit?: string | null
    amount?: string | number | null
  }> | null | undefined,
) {
  return (items ?? [])
    .map((item) => {
      const parts: string[] = []
      if (item.name?.trim()) parts.push(item.name.trim())
      if (!isEurUnit(item.unit) && item.quantity != null && item.quantity !== '') {
        parts.push(`${formatQuantity(item.quantity)} ${item.unit ?? ''}`.trim())
      }
      if (item.volume != null && item.volume !== '') {
        parts.push(`${tr('Litraža')} ${formatQuantity(item.volume)} ${item.volume_unit || 'L'}`.trim())
      }
      return parts.join(' ')
    })
    .filter(Boolean)
    .join(' · ')
}

export function formatMoney(amount: string | number | null | undefined, currency = 'EUR') {
  if (amount === null || amount === undefined || amount === '') {
    return new Intl.NumberFormat(activeLocale(), {
      style: 'currency',
      currency,
      minimumFractionDigits: 2,
    }).format(0)
  }
  const numeric = typeof amount === 'number' ? amount : Number(amount)
  if (Number.isNaN(numeric)) return '—'
  return new Intl.NumberFormat(activeLocale(), {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
  }).format(numeric)
}

export function formatChartMoney(amount: string | number | null | undefined, currency = 'EUR') {
  const numeric = amount === null || amount === undefined || amount === '' ? 0 : Number(amount)
  if (Number.isNaN(numeric)) return '—'
  const compact = Math.abs(numeric) >= 100
  return new Intl.NumberFormat(activeLocale(), {
    style: 'currency',
    currency,
    minimumFractionDigits: compact ? 0 : 2,
    maximumFractionDigits: compact ? 0 : 2,
  }).format(compact ? Math.round(numeric) : numeric)
}

/** Short amount for tight chart labels (no currency symbol). */
export function formatChartAmountShort(amount: string | number | null | undefined) {
  const numeric = amount === null || amount === undefined || amount === '' ? 0 : Number(amount)
  if (Number.isNaN(numeric)) return '—'
  const abs = Math.abs(numeric)
  if (abs >= 1000) {
    const value = numeric / 1000
    const digits = abs >= 10000 ? 0 : 1
    return `${new Intl.NumberFormat(activeLocale(), { maximumFractionDigits: digits }).format(value)}k`
  }
  return new Intl.NumberFormat(activeLocale(), { maximumFractionDigits: 0 }).format(Math.round(numeric))
}

export function formatDate(value: string) {
  const date = new Date(`${value}T00:00:00`)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat(activeLocale(), {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(date)
}

export function formatWeekday(value: string, short = false) {
  const date = new Date(`${value}T00:00:00`)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat(activeLocale(), { weekday: short ? 'short' : 'long' }).format(date)
}

export function formatDayMonth(value: string) {
  const date = new Date(`${value}T00:00:00`)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat(activeLocale(), { day: 'numeric', month: 'long' }).format(date)
}

export function isSameCalendarDay(value: string) {
  const date = new Date(`${value}T00:00:00`)
  if (Number.isNaN(date.getTime())) return false
  const now = new Date()
  return (
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate()
  )
}

export function formatUpdatedAt(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const time = new Intl.DateTimeFormat(activeLocale(), {
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
  const now = new Date()
  const sameDay =
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate()
  if (sameDay) return `${tr('danas u')} ${time}`
  return `${new Intl.DateTimeFormat(activeLocale(), {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }).format(date)}. ${time}`
}

export function formatKg(value: string | number | null | undefined, options?: { per?: string; digits?: number }) {
  if (value === null || value === undefined || value === '') return '—'
  const numeric = typeof value === 'number' ? value : Number(value)
  if (Number.isNaN(numeric)) return '—'
  const digits = options?.digits ?? (Math.abs(numeric) >= 100 ? 0 : 2)
  const formatted = numeric.toLocaleString(activeLocale(), {
    maximumFractionDigits: digits,
    minimumFractionDigits: 0,
  })
  return options?.per ? `${formatted} kg/${tr(options.per)}` : `${formatted} kg`
}

export function formatPercentValue(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === '') return '—'
  const numeric = typeof value === 'number' ? value : Number(value)
  if (Number.isNaN(numeric)) return '—'
  const prefix = numeric > 0 ? '+' : ''
  return `${prefix}${numeric.toLocaleString(activeLocale(), { maximumFractionDigits: 1 })}%`
}

export function rowLabel(rowNumber: number) {
  return `${tr('Red')} ${String(rowNumber).padStart(2, '0')}`
}

export function scopeLabel(scope: string) {
  if (scope === 'parcel') return tr('Parcela')
  if (scope === 'row') return tr('Red')
  if (scope === 'tree') return tr('Stablo')
  return scope
}

export function activityTarget(activity: {
  scope_type: string
  parcel_name: string | null
  row_number: number | null
  row_numbers?: number[] | null
  tree_public_id: string | null
}) {
  if (activity.scope_type === 'tree' && activity.tree_public_id) return activity.tree_public_id
  if (activity.scope_type === 'row') {
    const numbers = activity.row_numbers?.length
      ? activity.row_numbers
      : activity.row_number != null
        ? [activity.row_number]
        : []
    if (numbers.length === 1) return rowLabel(numbers[0]!)
    if (numbers.length > 1 && numbers.length <= 4) {
      return numbers.map((value) => String(value).padStart(2, '0')).join(', ')
    }
    if (numbers.length > 4) return `${numbers.length} ${tr('redova')}`
  }
  return activity.parcel_name ?? tr('Parcela')
}
