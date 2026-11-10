import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { getEnterpriseDataQuality } from '@/features/enterprise/api'
import { useEnterprise } from '@/features/enterprise/EnterpriseContext'
import { formatNumber } from '@/shared/lib/format'
import { cn } from '@/shared/lib/utils'

import { tr } from '@/shared/i18n/i18n'

const CARDS = [
  {
    key: 'usable_scene',
    labelKey: 'Kvalitetan snimak',
    hintKey: 'Bar jedna opservacija ispod 30% oblačnosti',
  },
  {
    key: 'cloudy_only',
    labelKey: 'Snimak bez kvaliteta',
    hintKey: 'Snimak postoji, nijedan nije ispod 30%',
  },
  { key: 'no_scene', labelKey: 'Bez snimka', hintKey: 'Nije dokaz lošeg stanja zasada' },
  {
    key: 'insufficient_history',
    labelKey: 'Kratka istorija',
    hintKey: 'Nema dve pouzdane opservacije za poređenje',
  },
  {
    key: 'open_alert',
    labelKey: 'Otvorena anomalija',
    hintKey: 'Alert je open ili acknowledged',
  },
  {
    key: 'incomplete',
    labelKey: 'Nepotpuni podaci',
    hintKey: 'Površina, sorta, godina sadnje ili stablo',
  },
] as const

type Bucket = (typeof CARDS)[number]['key']

export function EnterpriseDataQualitySection({ year }: { year: number }) {
  useTranslation()
  const { organizationId } = useEnterprise()
  const [bucket, setBucket] = useState<Bucket | null>(null)
  const query = useQuery({
    queryKey: ['enterprise-data-quality', organizationId, year, bucket],
    queryFn: () => getEnterpriseDataQuality(organizationId, year, bucket ?? undefined),
  })
  const data = query.data

  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-lg font-semibold">{tr('Kvalitet podataka')}</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Sezona {year}. Brojevi su nad dodeljenim parcelama, bez novog satelitskog zahteva.
        </p>
      </div>
      {query.isLoading ? (
        <p className="text-sm text-muted-foreground">{tr('Računanje pokrivenosti…')}</p>
      ) : query.isError ? (
        <p className="text-sm text-danger">{tr('Kvalitet podataka nije učitan.')}</p>
      ) : data ? (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {CARDS.map((card) => {
              const value = data[card.key]
              const active = bucket === card.key
              return (
                <button
                  key={card.key}
                  type="button"
                  className={cn(
                    'rounded-2xl border px-4 py-3 text-left',
                    active ? 'border-primary bg-primary/[0.06]' : 'border-border',
                  )}
                  onClick={() => setBucket(active ? null : card.key)}
                >
                  <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                    {tr(card.labelKey)}
                  </p>
                  <p className="mt-1 text-2xl font-semibold tabular-nums">{formatNumber(value)}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{tr(card.hintKey)}</p>
                </button>
              )
            })}
          </div>
          {bucket ? (
            data.parcels.length === 0 ? (
              <p className="text-sm text-muted-foreground">{tr('Nema parcela u ovoj grupi.')}</p>
            ) : (
              <ul className="divide-y divide-border rounded-2xl border border-border">
                {data.parcels.map((parcel) => (
                  <li key={parcel.parcel_id} className="px-4 py-2 text-sm">
                    <Link
                      to={`/enterprise/${organizationId}/parcels/${parcel.parcel_id}`}
                      className="font-medium hover:underline"
                    >
                      {parcel.parcel_name}
                    </Link>
                    <span className="text-muted-foreground">
                      {parcel.producer_name ? tr(' · {{name}}', { name: parcel.producer_name }) : ''}
                    </span>
                  </li>
                ))}
              </ul>
            )
          ) : null}
        </>
      ) : null}
    </section>
  )
}
