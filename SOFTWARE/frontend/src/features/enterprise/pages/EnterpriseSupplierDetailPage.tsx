import { lazy, Suspense, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'

import {
  getEnterpriseMapParcels,
  getEnterpriseSupplier,
  listEnterpriseParcels,
} from '@/features/enterprise/api'
import { useEnterprise } from '@/features/enterprise/EnterpriseContext'
import type { MapParcelItem } from '@/features/dashboard/ParcelsMap'
import { formatNumber } from '@/shared/lib/format'
import { Button } from '@/shared/ui/button'

import { tr } from '@/shared/i18n/i18n'
const ParcelsMap = lazy(async () => {
  const module = await import('@/features/dashboard/ParcelsMap')
  return { default: module.ParcelsMap }
})

export function EnterpriseSupplierDetailPage() {
  useTranslation()
  const { organizationId } = useEnterprise()
  const { linkId = '' } = useParams()
  const supplierQuery = useQuery({
    queryKey: ['enterprise-supplier', organizationId, linkId],
    queryFn: () => getEnterpriseSupplier(organizationId, linkId),
    enabled: Boolean(linkId),
  })
  const supplier = supplierQuery.data
  const parcelsQuery = useQuery({
    queryKey: ['enterprise-parcels', organizationId, supplier?.farm_id],
    queryFn: () => listEnterpriseParcels(organizationId, { farm_id: supplier!.farm_id }),
    enabled: Boolean(supplier?.farm_id),
  })
  const mapQuery = useQuery({
    queryKey: ['enterprise-map-parcels', organizationId],
    queryFn: () => getEnterpriseMapParcels(organizationId),
    enabled: Boolean(supplier?.farm_id),
  })

  const parcels = parcelsQuery.data ?? []
  const parcelIds = useMemo(() => new Set(parcels.map((p) => p.parcel_id)), [parcels])

  const mapParcels = useMemo<MapParcelItem[]>(() => {
    const fromMap = (mapQuery.data ?? []).filter((p) => parcelIds.has(p.parcel_id))
    if (fromMap.length > 0) {
      return fromMap.map((parcel) => ({
        id: parcel.parcel_id,
        name: parcel.parcel_name,
        latitude: String(parcel.latitude),
        longitude: String(parcel.longitude),
        tree_count: parcel.tree_count,
        area_hectares: parcel.area_hectares,
        issue_trees: parcel.issue_trees ?? 0,
        monitoring_trees: parcel.monitoring_trees ?? 0,
        open_cases: parcel.open_cases ?? 0,
      }))
    }
    return parcels
      .filter((p) => p.latitude != null && p.longitude != null)
      .map((parcel) => ({
        id: parcel.parcel_id,
        name: parcel.parcel_name,
        latitude: parcel.latitude != null ? String(parcel.latitude) : null,
        longitude: parcel.longitude != null ? String(parcel.longitude) : null,
        tree_count: parcel.tree_count,
        area_hectares: parcel.area_hectares,
        issue_trees: 0,
        monitoring_trees: 0,
        open_cases: 0,
      }))
  }, [mapQuery.data, parcelIds, parcels])

  if (supplierQuery.isLoading) {
    return <p className="text-sm text-muted-foreground">{tr('Učitavanje dobavljača…')}</p>
  }
  if (!supplier) {
    return <p className="text-sm text-danger">{tr('Dobavljač nije pronađen.')}</p>
  }

  const title =
    supplier.producer_display_name ||
    supplier.owner_full_name ||
    supplier.farm_name ||
    supplier.farm_id
  const base = `/enterprise/${organizationId}`

  return (
    <div className="flex min-h-full flex-1 flex-col gap-6">
      <div className="shrink-0">
        <Link to={`${base}/suppliers`} className="text-sm text-primary hover:underline">
          {tr('← Dobavljači')}
        </Link>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">{title}</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {supplier.farm_name && supplier.farm_name !== title
            ? tr('Zasad: {{name}} · ', { name: supplier.farm_name })
            : ''}
          {supplier.internal_code ? `Kod ${supplier.internal_code}` : tr('Bez internog koda')}
          {supplier.farm_location ? ` · ${supplier.farm_location}` : ''}
        </p>
      </div>

      <div className="grid shrink-0 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat
          label={tr('Parcele')}
          value={formatNumber(supplier.assigned_parcel_count)}
        />
        <Stat
          label={tr("Površina")}
          value={
            supplier.assigned_area_ha != null
              ? `${formatNumber(supplier.assigned_area_ha)} ha`
              : '—'
          }
        />
        <Stat
          label={tr("Očekivano")}
          value={
            supplier.expected_yield_kg != null
              ? `${formatNumber(supplier.expected_yield_kg)} kg`
              : '—'
          }
        />
        <Stat
          label={tr("Ostvareno")}
          value={
            supplier.actual_yield_kg != null
              ? `${formatNumber(supplier.actual_yield_kg)} kg`
              : '—'
          }
        />
      </div>

      {supplier.internal_notes ? (
        <div className="shrink-0 rounded-2xl border border-border px-4 py-3 text-sm">
          <p className="text-xs text-muted-foreground">{tr('Interne beleške')}</p>
          <p className="mt-1 whitespace-pre-wrap">{supplier.internal_notes}</p>
        </div>
      ) : null}

      <section className="flex min-h-0 flex-1 flex-col gap-3">
        <h2 className="shrink-0 text-sm font-semibold">{tr('Dodeljene parcele')}</h2>
        <div className="grid min-h-[280px] flex-1 gap-4 xl:grid-cols-3 xl:items-stretch">
          <div className="min-h-[240px] overflow-hidden rounded-2xl border border-border bg-card xl:col-span-2">
            {parcelsQuery.isLoading || mapQuery.isLoading ? (
              <div className="flex h-full items-center justify-center">
                <p className="text-sm text-muted-foreground">{tr('Učitavanje mape…')}</p>
              </div>
            ) : (
              <Suspense
                fallback={
                  <div className="flex h-full items-center justify-center">
                    <p className="text-sm text-muted-foreground">{tr('Učitavanje mape…')}</p>
                  </div>
                }
              >
                <ParcelsMap
                  className="h-full min-h-[240px] w-full rounded-none"
                  parcels={mapParcels}
                  getParcelHref={(parcel) => `${base}/parcels/${parcel.id}`}
                  emptyMessage={tr("Nema parcela sa koordinatama za ovog dobavljača.")}
                />
              </Suspense>
            )}
          </div>

          <div className="flex min-h-[240px] flex-col gap-2 overflow-y-auto">
            {parcelsQuery.isLoading ? (
              <p className="text-sm text-muted-foreground">{tr('Učitavanje zasada…')}</p>
            ) : parcels.length === 0 ? (
              <p className="rounded-2xl border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
                Nema dodeljenih parcela.
              </p>
            ) : (
              parcels.map((parcel) => {
                const varieties =
                  parcel.variety_names?.length > 0
                    ? parcel.variety_names
                    : parcel.default_variety
                      ? [parcel.default_variety]
                      : []
                return (
                  <article
                    key={parcel.parcel_id}
                    className="flex min-h-0 flex-1 flex-col rounded-2xl border border-border bg-card px-3 py-2.5"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <h3 className="truncate text-sm font-semibold tracking-tight">
                          {parcel.parcel_name}
                          {parcel.default_planting_year != null
                            ? ` · ${parcel.default_planting_year}.`
                            : ''}
                        </h3>
                        <div className="mt-1 flex flex-wrap gap-1">
                          {varieties.length > 0 ? (
                            varieties.map((name) => (
                              <span
                                key={name}
                                className="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary"
                              >
                                {name}
                              </span>
                            ))
                          ) : (
                            <span className="text-xs text-muted-foreground">{tr('Sorte nisu unete')}</span>
                          )}
                        </div>
                      </div>
                      <Button asChild size="sm" variant="outline" className="shrink-0">
                        <Link to={`${base}/parcels/${parcel.parcel_id}`}>
                          Detalji
                          <ArrowRight className="ml-1 h-3.5 w-3.5" />
                        </Link>
                      </Button>
                    </div>

                    <div className="mt-2 grid grid-cols-2 gap-1.5 text-sm">
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
                    <p className="mt-auto pt-1.5 text-[11px] text-muted-foreground">
                      Completeness{' '}
                      <span className="font-semibold tabular-nums text-foreground">
                        {parcel.completeness_score != null
                          ? `${formatNumber(parcel.completeness_score)}%`
                          : '—'}
                      </span>
                    </p>
                  </article>
                )
              })
            )}
          </div>
        </div>
      </section>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border px-4 py-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-xl font-semibold tabular-nums">{value}</p>
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-muted/40 px-2 py-1.5">
      <p className="text-[9px] uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-0.5 text-sm font-semibold tabular-nums">{value}</p>
    </div>
  )
}
