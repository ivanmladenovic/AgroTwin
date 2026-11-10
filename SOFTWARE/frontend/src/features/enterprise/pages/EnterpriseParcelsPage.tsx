import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'

import { listEnterpriseParcels } from '@/features/enterprise/api'
import { useEnterprise } from '@/features/enterprise/EnterpriseContext'
import { formatNumber } from '@/shared/lib/format'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'

import { tr } from '@/shared/i18n/i18n'
export function EnterpriseParcelsPage() {
  useTranslation()
  const { organizationId } = useEnterprise()
  const [q, setQ] = useState('')
  const query = useQuery({
    queryKey: ['enterprise-parcels', organizationId, q],
    queryFn: () => listEnterpriseParcels(organizationId, { q: q || undefined }),
  })

  return (
    <div className="space-y-6">
      <div>
        <p className="kicker">{tr('Parcele')}</p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">{tr('Dodeljene parcele')}</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {tr('Kartice zasada sa svim sortama. Detalji, berba i tretmani dostupni su samo za čitanje.')}
        </p>
      </div>

      <Input
        placeholder={tr("Pretraga parcela, proizvođača ili gazdinstava")}
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />

      {query.isLoading ? (
        <p className="text-sm text-muted-foreground">{tr('Učitavanje…')}</p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {(query.data ?? []).map((parcel) => {
            const varieties =
              parcel.variety_names?.length > 0
                ? parcel.variety_names
                : parcel.default_variety
                  ? [parcel.default_variety]
                  : []
            return (
              <article
                key={parcel.parcel_id}
                className="flex flex-col rounded-2xl border border-border/80 bg-card p-4 shadow-sm"
              >
                <div className="min-w-0">
                  <h2 className="truncate text-lg font-semibold tracking-tight">
                    {parcel.parcel_name}
                    {parcel.default_planting_year != null
                      ? ` · ${parcel.default_planting_year}.`
                      : ''}
                  </h2>
                  <p className="mt-0.5 truncate text-sm text-muted-foreground">
                    {parcel.producer_display_name || parcel.farm_name}
                  </p>
                </div>

                <div className="mt-3 flex flex-wrap gap-1.5">
                  {varieties.length > 0 ? (
                    varieties.map((name) => (
                      <span
                        key={name}
                        className="rounded-full bg-primary/10 px-2.5 py-0.5 text-[11px] font-medium text-primary"
                      >
                        {name}
                      </span>
                    ))
                  ) : (
                    <span className="text-xs text-muted-foreground">{tr('Sorte nisu unete')}</span>
                  )}
                </div>

                <div className="mt-4 grid grid-cols-2 gap-2 text-sm">
                  <Metric
                    label={tr("Površina")}
                    value={
                      parcel.area_hectares != null
                        ? `${formatNumber(parcel.area_hectares)} ha`
                        : '—'
                    }
                  />
                  <Metric label={tr("Stabla")} value={formatNumber(parcel.tree_count)} />
                  <Metric
                    label={tr("Očekivano")}
                    value={
                      parcel.expected_yield_kg != null
                        ? `${formatNumber(parcel.expected_yield_kg)} kg`
                        : '—'
                    }
                  />
                  <Metric
                    label={tr("Poslednja berba")}
                    value={
                      parcel.latest_harvest_kg != null
                        ? `${formatNumber(parcel.latest_harvest_kg)} kg`
                        : '—'
                    }
                  />
                </div>

                <div className="mt-4 flex items-center justify-between gap-3 border-t border-border/60 pt-3">
                  <p className="text-xs text-muted-foreground">
                    Completeness{' '}
                    <span className="font-semibold tabular-nums text-foreground">
                      {parcel.completeness_score != null
                        ? `${formatNumber(parcel.completeness_score)}%`
                        : '—'}
                    </span>
                  </p>
                  <Button asChild size="sm" variant="outline">
                    <Link to={`/enterprise/${organizationId}/parcels/${parcel.parcel_id}`}>
                      Detalji
                      <ArrowRight className="ml-1 h-3.5 w-3.5" />
                    </Link>
                  </Button>
                </div>
              </article>
            )
          })}
          {(query.data ?? []).length === 0 ? (
            <p className="col-span-full rounded-2xl border border-dashed border-border px-4 py-10 text-center text-sm text-muted-foreground">
              Nema dodeljenih parcela.
            </p>
          ) : null}
        </div>
      )}
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-muted/40 px-3 py-2">
      <p className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-0.5 font-semibold tabular-nums">{value}</p>
    </div>
  )
}
