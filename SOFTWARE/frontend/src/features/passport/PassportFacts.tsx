import { formatDate } from '@/shared/lib/format'

import { tr } from '@/shared/i18n/i18n'
export function PassportFacts({
  producer,
  location,
  lotNumber,
  crop,
  varieties,
  harvestDate,
}: {
  producer: string | null | undefined
  location: string | null | undefined
  lotNumber: string
  crop: string | null | undefined
  varieties: string[]
  harvestDate: string | null | undefined
}) {
  const rows = [
    { label: tr('Proizvođač'), value: producer || '—' },
    { label: tr('Lokacija parcele'), value: location || '—' },
    { label: 'Broj lota', value: lotNumber },
    { label: 'Kultura', value: crop || '—' },
    { label: 'Sorte', value: varieties.length > 0 ? varieties.join(', ') : '—' },
    { label: tr('Datum berbe'), value: harvestDate ? formatDate(harvestDate) : '—' },
  ]

  return (
    <dl className="space-y-3 text-left">
      {rows.map((row) => (
        <div key={row.label}>
          <dt className="text-xs text-muted-foreground">{row.label}</dt>
          <dd className="text-sm font-medium">{row.value}</dd>
        </div>
      ))}
    </dl>
  )
}
