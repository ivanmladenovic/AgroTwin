import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'

import { getEnterpriseParcel, getEnterpriseParcelTwin } from '@/features/enterprise/api'
import { useEnterprise } from '@/features/enterprise/EnterpriseContext'
import { OrchardSatelliteMap } from '@/features/orchard/OrchardSatelliteMap'
import { formatNumber } from '@/shared/lib/format'

import { tr } from '@/shared/i18n/i18n'
export function EnterpriseParcelDetailPage() {
  useTranslation()
  const { organizationId } = useEnterprise()
  const { parcelId = '' } = useParams()
  const query = useQuery({
    queryKey: ['enterprise-parcel', organizationId, parcelId],
    queryFn: () => getEnterpriseParcel(organizationId, parcelId),
    enabled: Boolean(parcelId),
  })
  const twinQuery = useQuery({
    queryKey: ['enterprise-parcel-twin', organizationId, parcelId],
    queryFn: () => getEnterpriseParcelTwin(organizationId, parcelId),
    enabled: Boolean(parcelId),
  })
  const parcel = query.data

  if (query.isLoading) return <p className="text-sm text-muted-foreground">{tr('Učitavanje parcele…')}</p>
  if (!parcel) return <p className="text-sm text-danger">{tr('Parcela nije dostupna.')}</p>

  const varieties =
    parcel.variety_names?.length > 0
      ? parcel.variety_names
      : parcel.default_variety
        ? [parcel.default_variety]
        : []
  const harvestRows = parcel.harvest_by_year ?? []

  return (
    <div className="space-y-8">
      <div className="relative overflow-hidden rounded-3xl border border-border/70 bg-gradient-to-br from-[#edf4ef] via-card to-[#eef2f0] px-5 py-6 sm:px-7 sm:py-7">
        <Link
          to={`/enterprise/${organizationId}/parcels`}
          className="text-sm font-medium text-primary hover:underline"
        >
          ← Parcele
        </Link>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight">
          {parcel.parcel_name}
          {parcel.default_planting_year != null ? ` · ${parcel.default_planting_year}.` : ''}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {parcel.producer_display_name || parcel.farm_name}
          {parcel.producer_display_name && parcel.farm_name !== parcel.producer_display_name
            ? ` · ${parcel.farm_name}`
            : ''}
        </p>
        <div className="mt-4 flex flex-wrap gap-1.5">
          {varieties.map((name) => (
            <span
              key={name}
              className="rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary"
            >
              {name}
            </span>
          ))}
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat
          label={tr("Površina")}
          value={parcel.area_hectares != null ? `${formatNumber(parcel.area_hectares)} ha` : '—'}
        />
        <Stat label={tr("Stabla")} value={formatNumber(parcel.tree_count)} />
        <Stat
          label={tr("Očekivani prinos")}
          value={
            parcel.expected_yield_kg != null ? `${formatNumber(parcel.expected_yield_kg)} kg` : '—'
          }
        />
        <Stat
          label={tr("Poslednja berba")}
          value={
            parcel.latest_harvest_kg != null
              ? `${formatNumber(parcel.latest_harvest_kg)} kg`
              : tr('Nije dostupno')
          }
        />
        {parcel.row_count != null ? (
          <Stat label="Redovi" value={formatNumber(parcel.row_count)} />
        ) : null}
        {parcel.trees_per_row != null ? (
          <Stat label={tr('Stabala po redu')} value={formatNumber(parcel.trees_per_row)} />
        ) : null}
        {parcel.default_planting_year != null ? (
          <Stat label={tr('Godina sadnje')} value={String(parcel.default_planting_year)} />
        ) : null}
        {parcel.completeness_score != null ? (
          <Stat label="Completeness" value={`${formatNumber(parcel.completeness_score)}%`} />
        ) : null}
      </div>

      {parcel.missing_fields.length > 0 ? (
        <div className="rounded-2xl border border-amber-300/50 bg-amber-50 px-4 py-3 text-sm text-amber-950">
          Nedostaju polja: {parcel.missing_fields.join(', ')}
        </div>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MiniStat label="Tretmani" value={formatNumber(parcel.protection_count ?? 0)} />
        <MiniStat label={tr("Đubrenje")} value={formatNumber(parcel.fertilization_count ?? 0)} />
        <MiniStat label={tr("Navodnjavanje")} value={formatNumber(parcel.irrigation_count ?? 0)} />
        <MiniStat label="Posmatranja / problemi" value={formatNumber(parcel.observation_count ?? 0)} />
      </div>

      <div className="grid gap-4 xl:grid-cols-3 xl:items-start">
        <section className="space-y-2 xl:col-span-2">
          <h2 className="text-sm font-semibold">{tr('Satelitski pregled')}</h2>
          <div className="relative aspect-[5/4] w-full max-h-[min(52vh,28rem)] overflow-hidden rounded-2xl border border-border bg-muted sm:aspect-square sm:max-h-[26rem]">
            {twinQuery.isLoading ? (
              <div className="absolute inset-0 flex items-center justify-center text-sm text-muted-foreground">
                {tr('Učitavanje mape…')}
              </div>
            ) : twinQuery.isError ? (
              <div className="absolute inset-0 flex items-center justify-center px-4 text-center text-sm text-danger">
                {tr('Mapa nije učitana. Osvežite stranicu ili proverite dodele parcela.')}
              </div>
            ) : twinQuery.data ? (
              <OrchardSatelliteMap
                twin={twinQuery.data}
                selectedTreeId={null}
                className="absolute inset-0 h-full w-full"
              />
            ) : (
              <div className="absolute inset-0 flex items-center justify-center px-4 text-center text-sm text-muted-foreground">
                Mapa nije dostupna za ovu parcelu.
              </div>
            )}
          </div>
          <p className="text-xs text-muted-foreground">
            {tr('Enterprise ne može da menja granicu, stabla ni sorte. Prikaz je isključivo informativan.')}
          </p>
        </section>

        <section className="flex flex-col gap-3 sm:max-h-[26rem]">
          <h2 className="text-sm font-semibold">{tr('Berba po godinama')}</h2>
          {harvestRows.length === 0 ? (
            <div className="flex flex-1 items-center justify-center rounded-2xl border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
              Nema evidentiranih berbi.
            </div>
          ) : (
            <div className="flex flex-col gap-3 overflow-y-auto">
              {harvestRows.map((row) => (
                <article
                  key={row.year}
                  className="rounded-2xl border border-border bg-card px-4 py-4"
                >
                  <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                    Sezona {row.year}.
                  </p>
                  <p className="mt-1.5 text-2xl font-semibold tabular-nums tracking-tight">
                    {row.net_kg != null ? `${formatNumber(row.net_kg)} kg` : '—'}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {row.event_count > 0
                      ? tr('{{count}} evidentiranih berbi', { count: formatNumber(row.event_count) })
                      : tr('Bez događaja')}
                  </p>
                </article>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border/80 bg-card px-4 py-3">
      <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
        {label}
      </p>
      <p className="mt-1.5 text-lg font-semibold tabular-nums">{value}</p>
    </div>
  )
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl bg-muted/40 px-4 py-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-xl font-semibold tabular-nums">{value}</p>
    </div>
  )
}
