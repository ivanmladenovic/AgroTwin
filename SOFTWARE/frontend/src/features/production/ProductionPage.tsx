import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Plus } from 'lucide-react'

import { listParcels } from '@/features/orchard/api'
import { PhotoGallery } from '@/features/health/PhotoGallery'
import { downloadProductionCsv, getParcelProduction } from '@/features/production/api'
import { qualityLabel } from '@/features/production/labels'
import {
  formatDate,
  formatKg,
  formatNumber,
  formatPercentValue,
  rowLabel,
  scopeLabel,
} from '@/shared/lib/format'
import { cn } from '@/shared/lib/utils'
import type {
  ExpectedYield,
  ParcelProduction,
  ReportOptionalAmount,
  ReportYearChange,
  TreeStatus,
} from '@/shared/api/types'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'
import { Label } from '@/shared/ui/label'
import { Select } from '@/shared/ui/select'
import { tr } from '@/shared/i18n/i18n'

type RowSort = 'number' | 'high' | 'low'
type TreeSort = 'high' | 'low'
type TreeStatusFilter = 'all' | TreeStatus

export function ProductionPage() {
  const { i18n } = useTranslation()
  void i18n.language
  const { parcelId: routeParcelId } = useParams()
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const parcelsQuery = useQuery({ queryKey: ['parcels'], queryFn: listParcels })
  const parcels = parcelsQuery.data ?? []
  const selectedParcelId = routeParcelId || params.get('parcelId') || parcels[0]?.id || ''
  const requestedYear = Number(params.get('year') || '')
  const fallbackYear = new Date().getFullYear()
  const year = Number.isInteger(requestedYear) && requestedYear >= 1990 ? requestedYear : fallbackYear
  const productionQuery = useQuery({
    queryKey: ['parcel-production', selectedParcelId, year],
    queryFn: () => getParcelProduction(selectedParcelId, year),
    enabled: Boolean(selectedParcelId),
  })
  const production = productionQuery.data
  const years = useMemo(() => {
    const collected = new Set(production?.available_years ?? [])
    collected.add(year)
    collected.add(fallbackYear)
    collected.add(fallbackYear - 1)
    collected.add(fallbackYear + 1)
    return [...collected].sort((a, b) => a - b)
  }, [fallbackYear, production, year])

  function updateYear(nextYear: number) {
    const next = new URLSearchParams(params)
    next.set('year', String(nextYear))
    setParams(next, { replace: true })
  }

  function updateParcel(nextParcelId: string) {
    if (routeParcelId) {
      navigate(`/orchard/${nextParcelId}/production?year=${year}`)
      return
    }
    const next = new URLSearchParams(params)
    next.set('parcelId', nextParcelId)
    next.set('year', String(year))
    setParams(next, { replace: true })
  }

  if (!selectedParcelId && !parcelsQuery.isLoading) {
    return <p className="text-sm text-muted-foreground">{tr('Nema parcele za proizvodnju. Prvo napravite zasad.')}</p>
  }

  const addHref = selectedParcelId ? `/orchard/${selectedParcelId}/production/new?year=${year}` : ''

  return (
    <div className="w-full space-y-6 pb-20 sm:pb-0">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="kicker">{tr("Proizvodnja")}</p>
          <h1 className="mt-1 text-xl font-semibold sm:text-2xl">{tr("Proizvodnja")}</h1>
          <p className="mt-2 text-sm text-muted-foreground">{tr('Pregled berbe i prinosa parcele.')}</p>
        </div>
        <div className="hidden gap-2 sm:flex">
          {selectedParcelId ? (
            <Button variant="outline" onClick={() => void downloadProductionCsv(selectedParcelId, year)}>
              {tr('Izvezi CSV')}
            </Button>
          ) : null}
          {addHref ? (
            <Link to={addHref}>
              <Button>
                <Plus className="h-4 w-4" />
                {tr('Dodaj berbu')}
              </Button>
            </Link>
          ) : null}
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-[1fr_10rem]">
        <div className="space-y-1.5">
          <Label>{tr("Parcela")}</Label>
          <Select value={selectedParcelId} onChange={(event) => updateParcel(event.target.value)}>
            {parcels.map((parcel) => (
              <option key={parcel.id} value={parcel.id}>
                {parcel.name}
              </option>
            ))}
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label>{tr('Godina')}</Label>
          <Select value={String(year)} onChange={(event) => updateYear(Number(event.target.value))}>
            {years.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </Select>
        </div>
      </div>

      {productionQuery.isLoading ? (
        <p className="text-sm text-muted-foreground">{tr('Učitavanje proizvodnje…')}</p>
      ) : productionQuery.isError || !production ? (
        <p className="text-sm text-danger">{tr('Proizvodnja nije učitana. Osvežite stranicu.')}</p>
      ) : (
        <div className="space-y-6">
          <ExpectedYieldScenariosSection expected={production.expected_yield} year={production.year} />
          <ExpectedYieldComparisonSection expected={production.expected_yield} year={production.year} />
          {!production.recorded ? (
            <EmptyState year={year} href={addHref} />
          ) : (
            <ProductionBody production={production} />
          )}
        </div>
      )}

      {addHref ? (
        <div className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-background/95 p-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] sm:hidden">
          <Link to={addHref}>
            <Button className="h-12 w-full">
              <Plus className="h-4 w-4" />
              {tr('Dodaj berbu')}
            </Button>
          </Link>
        </div>
      ) : null}
    </div>
  )
}

function EmptyState({ year, href }: { year: number; href: string }) {
  return (
    <Card>
      <CardContent className="space-y-4 py-10 text-center">
        <p className="text-base font-medium">{tr('Nema zabeležene berbe za {{year}}.', { year })}</p>
        <p className="mx-auto max-w-md text-sm text-muted-foreground">
          {tr(
            'Kada unesete berbu, AgroTwin će izračunati ukupan prinos, prinos po hektaru i godišnje trendove proizvodnje.',
          )}
        </p>
        {href ? (
          <Link to={href}>
            <Button>
              <Plus className="h-4 w-4" />
              {tr('Dodaj berbu')}
            </Button>
          </Link>
        ) : null}
      </CardContent>
    </Card>
  )
}

function ProductionBody({ production }: { production: ParcelProduction }) {
  const [params, setParams] = useSearchParams()
  const [rowSort, setRowSort] = useState<RowSort>(() => parseRowSort(params.get('rowSort')))
  const [treeSort, setTreeSort] = useState<TreeSort>(() => (params.get('treeSort') === 'low' ? 'low' : 'high'))
  const [treeRow, setTreeRow] = useState(() => params.get('treeRow') || '')
  const [treeStatus, setTreeStatus] = useState<TreeStatusFilter>(() => parseTreeStatus(params.get('treeStatus')))
  const parcelId = production.parcel_id
  const year = production.year

  useEffect(() => {
    const next = new URLSearchParams(params)
    if (rowSort === 'number') next.delete('rowSort')
    else next.set('rowSort', rowSort)
    if (treeSort === 'high') next.delete('treeSort')
    else next.set('treeSort', treeSort)
    if (treeRow) next.set('treeRow', treeRow)
    else next.delete('treeRow')
    if (treeStatus === 'all') next.delete('treeStatus')
    else next.set('treeStatus', treeStatus)
    if (next.toString() === params.toString()) return
    setParams(next, { replace: true })
  }, [params, rowSort, setParams, treeRow, treeSort, treeStatus])

  const rows = useMemo(() => {
    const items = [...production.row_summary]
    if (rowSort === 'high') items.sort((a, b) => Number(b.net_kg) - Number(a.net_kg))
    else if (rowSort === 'low') items.sort((a, b) => Number(a.net_kg) - Number(b.net_kg))
    else items.sort((a, b) => a.row_number - b.row_number)
    return items
  }, [production.row_summary, rowSort])

  const trees = useMemo(() => {
    const items = production.tree_summary.filter((item) => {
      if (treeRow && String(item.row_number) !== treeRow) return false
      if (treeStatus !== 'all' && item.tree_status !== treeStatus) return false
      return true
    })
    items.sort((a, b) => (treeSort === 'high' ? Number(b.net_kg) - Number(a.net_kg) : Number(a.net_kg) - Number(b.net_kg)))
    return items
  }, [production.tree_summary, treeRow, treeSort, treeStatus])

  return (
    <div className="space-y-6">
      <p className="text-xs text-muted-foreground">{tr(production.measurement_note)}</p>

      {production.parcel_total_recorded ? (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-6">
          <Kpi label={tr('Ukupan prinos')} value={formatKg(production.total_net_yield.value)} hint={tr('neto, nivo parcele')} />
          <Kpi
            label={tr('Berbe')}
            value={production.harvest_event_count != null ? formatNumber(production.harvest_event_count) : '—'}
          />
          <Kpi
            label={tr('Prinos / ha')}
            value={amountOrDash(production.yield_per_hectare, (value) => formatKg(value, { per: 'ha', digits: 0 }))}
          />
          <Kpi
            label={tr('Prinos / stablo')}
            value={amountOrDash(production.yield_per_tree, (value) => formatKg(value, { per: 'stablo' }))}
            hint={
              production.yield_per_tree_denominator === 'active_trees'
                ? tr('{{count}} aktivnih stabala', { count: formatNumber(production.active_trees) })
                : undefined
            }
          />
          <Kpi
            label={tr('Prva berba')}
            value={production.first_harvest_date ? formatDate(production.first_harvest_date) : tr('Nema zabeležene berbe')}
          />
          <Kpi
            label={tr('Poslednja berba')}
            value={production.last_harvest_date ? formatDate(production.last_harvest_date) : tr('Nema zabeležene berbe')}
          />
        </div>
      ) : (
        <Card>
          <CardContent className="py-4 text-sm text-muted-foreground">
            {tr(
              'Nema berbe na nivou parcele za {{year}}. Uneti su samo zapisi redova ili stabala, pa se ukupan prinos parcele ne sabira.',
              { year },
            )}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-3">
          <CardTitle>{tr('Zapisi berbe')}</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full min-w-[36rem] text-left text-sm">
            <thead className="text-xs uppercase tracking-wide text-muted-foreground">
              <tr className="border-b border-border">
                <th className="py-2 font-semibold">{tr('Datum')}</th>
                <th className="py-2 font-semibold">{tr('Obuhvat')}</th>
                <th className="py-2 font-semibold">{tr('Lokacija')}</th>
                <th className="py-2 text-right font-semibold">{tr('Bruto')}</th>
                <th className="py-2 text-right font-semibold">{tr('Gubitak')}</th>
                <th className="py-2 text-right font-semibold">{tr('Neto')}</th>
              </tr>
            </thead>
            <tbody>
              {production.events.map((event) => (
                <tr key={event.id} className="border-b border-border/70 last:border-0">
                  <td className="py-2.5">
                    <Link to={`/orchard/${parcelId}/production/${event.id}?year=${year}`} className="font-medium hover:underline">
                      {formatDate(event.harvested_on)}
                    </Link>
                  </td>
                  <td className="py-2.5">{scopeLabel(event.scope_type)}</td>
                  <td className="py-2.5">{event.location_label}</td>
                  <td className="py-2.5 text-right font-mono">{formatKg(event.gross_kg ?? event.gross_quantity)}</td>
                  <td className="py-2.5 text-right font-mono">{formatKg(event.loss_kg ?? event.loss_quantity)}</td>
                  <td className="py-2.5 text-right font-mono">{formatKg(event.net_kg ?? event.net_quantity)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

      {production.timeline.length > 0 ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>{tr('Tok berbe')}</CardTitle>
            </CardHeader>
            <CardContent>
              <HarvestBars points={production.timeline} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>{tr('Kumulativni prinos')}</CardTitle>
            </CardHeader>
            <CardContent>
              <CumulativeChart points={production.timeline} />
            </CardContent>
          </Card>
        </div>
      ) : null}

      <ComparisonCard production={production} />

      {production.quality_summary.recorded ? <QualityCard production={production} /> : null}

      {rows.length > 0 ? (
        <Card>
          <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <CardTitle>{tr('Prinos po redu')}</CardTitle>
            <Select value={rowSort} onChange={(event) => setRowSort(event.target.value as RowSort)} className="sm:w-48">
              <option value="number">{tr('Po broju reda')}</option>
              <option value="high">{tr('Najveći prinos')}</option>
              <option value="low">{tr('Najmanji prinos')}</option>
            </Select>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full min-w-[28rem] text-left text-sm">
              <thead className="text-xs uppercase tracking-wide text-muted-foreground">
                <tr className="border-b border-border">
                  <th className="py-2 font-semibold">{tr("Red")}</th>
                  <th className="py-2 text-right font-semibold">{tr('Prinos')}</th>
                  <th className="py-2 text-right font-semibold">{tr('Stabla')}</th>
                  <th className="py-2 text-right font-semibold">{tr('kg/stablo')}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.row_id} className="border-b border-border/70 last:border-0">
                    <td className="py-2.5">
                      <Link to={`/orchard/${parcelId}?row=${row.row_number}`} className="font-medium hover:underline">
                        {rowLabel(row.row_number)}
                      </Link>
                    </td>
                    <td className="py-2.5 text-right font-mono">{formatKg(row.net_kg)}</td>
                    <td className="py-2.5 text-right font-mono">{formatNumber(row.active_trees)}</td>
                    <td className="py-2.5 text-right font-mono">
                      {row.yield_per_tree.available ? formatKg(row.yield_per_tree.value) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      ) : null}

      {production.tree_summary.length > 0 ? (
        <Card>
          <CardHeader className="space-y-3">
            <CardTitle>{tr('Prinos po stablu')}</CardTitle>
            <div className="grid gap-2 sm:grid-cols-3">
              <Select value={treeRow} onChange={(event) => setTreeRow(event.target.value)}>
                <option value="">{tr('Svi redovi')}</option>
                {[...new Set(production.tree_summary.map((item) => item.row_number))]
                  .sort((a, b) => a - b)
                  .map((number) => (
                    <option key={number} value={String(number)}>
                      {rowLabel(number)}
                    </option>
                  ))}
              </Select>
              <Select value={treeSort} onChange={(event) => setTreeSort(event.target.value as TreeSort)}>
                <option value="high">{tr('Najveći prinos')}</option>
                <option value="low">{tr('Najmanji prinos')}</option>
              </Select>
              <Select value={treeStatus} onChange={(event) => setTreeStatus(event.target.value as TreeStatusFilter)}>
                <option value="all">{tr('Svi statusi')}</option>
                <option value="active">{tr('Aktivno')}</option>
                <option value="replaced">{tr('Zamenjeno')}</option>
                <option value="removed">{tr('Uklonjeno')}</option>
              </Select>
            </div>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full min-w-[24rem] text-left text-sm">
              <thead className="text-xs uppercase tracking-wide text-muted-foreground">
                <tr className="border-b border-border">
                  <th className="py-2 font-semibold">{tr("Stablo")}</th>
                  <th className="py-2 font-semibold">{tr("Red")}</th>
                  <th className="py-2 text-right font-semibold">{tr('Prinos')}</th>
                </tr>
              </thead>
              <tbody>
                {trees.map((tree) => (
                  <tr key={tree.tree_id} className="border-b border-border/70 last:border-0">
                    <td className="py-2.5">
                      <Link to={`/orchard/${parcelId}/trees/${tree.tree_id}`} className="font-medium hover:underline">
                        {tree.public_id}
                      </Link>
                    </td>
                    <td className="py-2.5">{rowLabel(tree.row_number)}</td>
                    <td className="py-2.5 text-right font-mono">{formatKg(tree.net_kg)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      ) : null}

      {production.photos.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>{tr('Najnovije fotografije berbe')}</CardTitle>
          </CardHeader>
          <CardContent>
            <PhotoGallery photos={production.photos} />
          </CardContent>
        </Card>
      ) : null}
    </div>
  )
}

function ComparisonCard({ production }: { production: ParcelProduction }) {
  const comparison = production.comparison
  if (!comparison.available) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>
            {tr('{{year}}. naspram {{previous}}.', { year: production.year, previous: comparison.previous_year })}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            {comparison.message ? tr(comparison.message) : tr('Nema podataka o berbi za prethodnu godinu.')}
          </p>
        </CardContent>
      </Card>
    )
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          {tr('{{year}}. naspram {{previous}}.', { year: production.year, previous: comparison.previous_year })}
        </CardTitle>
      </CardHeader>
      <CardContent className="grid gap-3 sm:grid-cols-3">
        <CompareStat
          label={tr('Ukupan prinos')}
          previous={formatKg(comparison.previous_net_yield.value)}
          current={formatKg(production.total_net_yield.value)}
          change={comparison.net_yield_change}
          previousYear={comparison.previous_year}
        />
        <CompareStat
          label={tr('Prinos / ha')}
          previous={amountOrDash(comparison.previous_yield_per_hectare, (value) => formatKg(value, { per: 'ha', digits: 0 }))}
          current={amountOrDash(production.yield_per_hectare, (value) => formatKg(value, { per: 'ha', digits: 0 }))}
          change={comparison.yield_per_hectare_change}
          previousYear={comparison.previous_year}
        />
        <CompareStat
          label={tr('Berbe')}
          previous={comparison.previous_harvest_event_count != null ? formatNumber(comparison.previous_harvest_event_count) : '—'}
          current={production.harvest_event_count != null ? formatNumber(production.harvest_event_count) : '—'}
          change={comparison.harvest_event_count_change}
          previousYear={comparison.previous_year}
        />
      </CardContent>
    </Card>
  )
}

function QualityCard({ production }: { production: ParcelProduction }) {
  const quality = production.quality_summary
  return (
    <Card>
      <CardHeader>
        <CardTitle>{tr('Kvalitet berbe')}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Mini label={tr("Prosečna vlažnost")} value={avgText(quality.moisture)} />
          <Mini label={tr("Oštećeni plodovi")} value={avgText(quality.damaged)} />
          <Mini label={tr('Prazni plodovi')} value={avgText(quality.empty_nuts)} />
          <Mini label={tr('Strane materije')} value={avgText(quality.foreign_material)} />
        </div>
        {quality.categories.length > 0 ? (
          <div className="space-y-2">
            {quality.categories.map((item) => (
              <div key={item.category} className="flex items-center justify-between text-sm">
                <span>{qualityLabel(item.category)}</span>
                <span className="font-mono">{formatKg(item.net_kg)}</span>
              </div>
            ))}
          </div>
        ) : null}
        <p className="text-xs text-muted-foreground">{tr('Proseci su ponderisani neto količinom berbe.')}</p>
      </CardContent>
    </Card>
  )
}

function HarvestBars({
  points,
}: {
  points: ParcelProduction['timeline']
}) {
  const max = Math.max(...points.map((item) => Number(item.net_kg)), 0)
  return (
    <div className="flex h-44 items-end gap-2">
      {points.map((point) => {
        const amount = Number(point.net_kg)
        const height = max > 0 ? Math.max((amount / max) * 100, 8) : 2
        return (
          <div key={point.harvested_on} className="flex min-w-0 flex-1 flex-col items-center gap-2">
            <p className="text-[11px] font-mono text-muted-foreground">{formatKg(point.net_kg, { digits: 0 })}</p>
            <div className="flex h-28 w-full items-end">
              <div className="w-full rounded-t-md bg-primary/80" style={{ height: `${height}%` }} />
            </div>
            <span className="text-[11px] text-muted-foreground">{formatDate(point.harvested_on)}</span>
          </div>
        )
      })}
    </div>
  )
}

function CumulativeChart({ points }: { points: ParcelProduction['timeline'] }) {
  const max = Math.max(...points.map((item) => Number(item.cumulative_net_kg)), 0)
  return (
    <div className="space-y-3">
      {points.map((point) => {
        const width = max > 0 ? Math.max((Number(point.cumulative_net_kg) / max) * 100, 8) : 0
        return (
          <div key={point.harvested_on} className="space-y-1">
            <div className="flex items-baseline justify-between gap-3 text-xs">
              <span>{formatDate(point.harvested_on)}</span>
              <span className="font-mono">{formatKg(point.cumulative_net_kg)}</span>
            </div>
            <div className="h-2 overflow-hidden rounded bg-muted">
              <div className="h-full rounded bg-accent" style={{ width: `${width}%` }} />
            </div>
          </div>
        )
      })}
    </div>
  )
}

function shellToNetPercentLabel(ratio: string): string {
  const numeric = Number(ratio)
  if (Number.isNaN(numeric)) return '40%'
  return `${Math.round(numeric * 100)}%`
}

function curveSeasonYear(ageYear: number, selectedYear: number, anchorAge: number | null) {
  if (anchorAge == null) return null
  return selectedYear - anchorAge + ageYear
}

function ExpectedYieldScenariosSection({ expected, year }: { expected: ExpectedYield; year: number }) {
  if (!expected.available) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{tr('Scenariji prinosa')}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          <p>
            {expected.message
              ? tr(expected.message)
              : tr('Nema dovoljno podataka o starosti zasada za izračunavanje očekivanog prinosa.')}
          </p>
          {expected.precision_note ? <p>{tr(expected.precision_note)}</p> : null}
        </CardContent>
      </Card>
    )
  }

  const netShare = shellToNetPercentLabel(expected.shell_to_net_ratio)
  const anchorAge =
    expected.age_years.length === 1
      ? expected.age_years[0]
      : (expected.curve.find((row) => row.is_current)?.age_year ?? null)

  return (
    <Card>
      <CardHeader>
        <CardTitle>{tr('Scenariji prinosa')}</CardTitle>
        {expected.age_label ? <p className="text-sm text-muted-foreground">{tr(expected.age_label)}</p> : null}
        <p className="text-sm text-muted-foreground">
          {tr('Vrednosti su bruto (kg ploda u ljusci). Neto za poređenje = {{share}} bruto.', {
            share: netShare,
          })}
        </p>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Kpi
            label={tr('Pesimistični')}
            value={amountOrDash(expected.pessimistic_kg, formatKg)}
            hint={tr('bruto u ljusci')}
          />
          <Kpi
            label={tr('Realistični')}
            value={amountOrDash(expected.realistic_kg, formatKg)}
            hint={tr('bruto za {{year}}.', { year })}
          />
          <Kpi
            label={tr('Optimistični')}
            value={amountOrDash(expected.optimistic_kg, formatKg)}
            hint={tr('bruto u ljusci')}
          />
          <Kpi
            label={tr('Po stablu')}
            value={amountOrDash(expected.expected_per_tree_realistic, (value) =>
              formatKg(value, { per: 'stablo' }),
            )}
            hint={
              expected.expected_per_hectare_realistic.available
                ? amountOrDash(expected.expected_per_hectare_realistic, (value) =>
                    formatKg(value, { per: 'ha', digits: 0 }),
                  )
                : tr('bruto / stablo')
            }
          />
        </div>

        {expected.precision_note ? (
          <p className="text-xs text-muted-foreground">{tr(expected.precision_note)}</p>
        ) : null}

        <ExpectedYieldChart curve={expected.curve} />

        <div className="overflow-x-auto">
          <table className="w-full min-w-[32rem] text-left text-sm">
            <thead className="text-xs uppercase tracking-wide text-muted-foreground">
              <tr className="border-b border-border">
                <th className="py-2 font-semibold">{tr('Sezona')}</th>
                <th className="py-2 font-semibold">{tr('Starost')}</th>
                <th className="py-2 text-right font-semibold">{tr('Pesimistični')}</th>
                <th className="py-2 text-right font-semibold">{tr('Realistični')}</th>
                <th className="py-2 text-right font-semibold">{tr('Optimistični')}</th>
              </tr>
            </thead>
            <tbody>
              {expected.curve.map((row) => {
                const season = curveSeasonYear(row.age_year, year, anchorAge)
                return (
                  <tr
                    key={row.age_year}
                    className={cn(
                      'border-b border-border/70 last:border-0',
                      row.is_current ? 'bg-accent/10 font-medium' : undefined,
                    )}
                  >
                    <td className="py-2 font-mono">{season ?? '—'}</td>
                    <td className="py-2">{row.age_year}.</td>
                    <td className="py-2 text-right font-mono">{formatKg(row.pessimistic)}</td>
                    <td className="py-2 text-right font-mono">{formatKg(row.realistic)}</td>
                    <td className="py-2 text-right font-mono">{formatKg(row.optimistic)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          <p className="mt-2 text-xs text-muted-foreground">
            {tr('Jedinica: kg u ljusci / stablo (bruto)')}
          </p>
        </div>

        {(expected.by_variety ?? []).length > 0 ? (
          <div className="overflow-x-auto">
            <p className="mb-2 text-sm font-medium">{tr('Očekivano po sortama (bruto)')}</p>
            <table className="w-full min-w-[36rem] text-left text-sm">
              <thead className="text-xs uppercase tracking-wide text-muted-foreground">
                <tr className="border-b border-border">
                  <th className="py-2 font-semibold">{tr('Sorta')}</th>
                  <th className="py-2 text-right font-semibold">{tr('Stabla')}</th>
                  <th className="py-2 text-right font-semibold">{tr('Udeo')}</th>
                  <th className="py-2 text-right font-semibold">{tr('Pesimistični')}</th>
                  <th className="py-2 text-right font-semibold">{tr('Realistični')}</th>
                  <th className="py-2 text-right font-semibold">{tr('Optimistični')}</th>
                </tr>
              </thead>
              <tbody>
                {expected.by_variety.map((row) => (
                  <tr key={row.variety} className="border-b border-border/70 last:border-0">
                    <td className="py-2">{row.variety}</td>
                    <td className="py-2 text-right font-mono">{formatNumber(row.tree_count)}</td>
                    <td className="py-2 text-right font-mono">
                      {row.share_of_trees_percent != null
                        ? `${formatNumber(row.share_of_trees_percent)}%`
                        : '—'}
                    </td>
                    <td className="py-2 text-right font-mono">
                      {amountOrDash(row.pessimistic_kg, formatKg)}
                    </td>
                    <td className="py-2 text-right font-mono">
                      {amountOrDash(row.realistic_kg, formatKg)}
                    </td>
                    <td className="py-2 text-right font-mono">
                      {amountOrDash(row.optimistic_kg, formatKg)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}

        {expected.cohorts.length > 1 ? (
          <div className="overflow-x-auto">
            <p className="mb-2 text-sm font-medium">{tr('Starosne grupe (bruto)')}</p>
            <table className="w-full min-w-[32rem] text-left text-sm">
              <thead className="text-xs uppercase tracking-wide text-muted-foreground">
                <tr className="border-b border-border">
                  <th className="py-2 font-semibold">{tr('Sadnja')}</th>
                  <th className="py-2 font-semibold">{tr('Starost')}</th>
                  <th className="py-2 text-right font-semibold">{tr('Stabla')}</th>
                  <th className="py-2 text-right font-semibold">{tr('Realistično / stablo')}</th>
                  <th className="py-2 text-right font-semibold">{tr('Ukupno')}</th>
                </tr>
              </thead>
              <tbody>
                {expected.cohorts.map((cohort) => (
                  <tr
                    key={`${cohort.planting_year}-${cohort.age_year}`}
                    className="border-b border-border/70 last:border-0"
                  >
                    <td className="py-2">{cohort.planting_year}</td>
                    <td className="py-2">{cohort.age_year}.</td>
                    <td className="py-2 text-right font-mono">{formatNumber(cohort.tree_count)}</td>
                    <td className="py-2 text-right font-mono">{formatKg(cohort.realistic_kg_per_tree)}</td>
                    <td className="py-2 text-right font-mono">{formatKg(cohort.realistic_kg)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}

        {expected.disclaimer ? (
          <p className="text-xs leading-relaxed text-muted-foreground">{tr(expected.disclaimer)}</p>
        ) : null}
      </CardContent>
    </Card>
  )
}

function ExpectedYieldComparisonSection({ expected, year }: { expected: ExpectedYield; year: number }) {
  if (!expected.available) return null

  const netShare = shellToNetPercentLabel(expected.shell_to_net_ratio)

  return (
    <Card>
      <CardHeader>
        <CardTitle>{tr('Analitika i poređenje')}</CardTitle>
        <p className="text-sm text-muted-foreground">
          {tr('Poređenje stvarne neto berbe sa očekivanim netom ({{share}} bruto krive).', {
            share: netShare,
          })}
        </p>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Kpi
            label={tr('Očekivano neto')}
            value={amountOrDash(expected.realistic_net_kg, formatKg)}
            hint={tr('realistični × {{share}}', { share: netShare })}
          />
          <Kpi
            label={tr('Stvarna berba')}
            value={amountOrDash(expected.actual_net_kg, formatKg)}
            hint={tr('neto, nivo parcele')}
          />
          <Kpi
            label={tr('Razlika')}
            value={
              expected.difference_kg.available && expected.difference_kg.value != null
                ? formatKg(expected.difference_kg.value)
                : '—'
            }
            hint={
              expected.difference_percent.available && expected.difference_percent.value != null
                ? formatPercentValue(expected.difference_percent.value)
                : undefined
            }
          />
          <Kpi
            label={tr('Po stablu (neto)')}
            value={amountOrDash(expected.expected_per_tree_realistic_net, (value) =>
              formatKg(value, { per: 'stablo' }),
            )}
            hint={
              expected.expected_per_hectare_realistic_net.available
                ? amountOrDash(expected.expected_per_hectare_realistic_net, (value) =>
                    formatKg(value, { per: 'ha', digits: 0 }),
                  )
                : undefined
            }
          />
        </div>

        {expected.comparison_message ? (
          <p className="text-sm text-muted-foreground">{tr(expected.comparison_message)}</p>
        ) : null}

        {expected.history.length > 0 ? (
          <div className="overflow-x-auto">
            <p className="mb-2 text-sm font-medium">{tr('Poređenje po godinama (neto)')}</p>
            <table className="w-full min-w-[32rem] text-left text-sm">
              <thead className="text-xs uppercase tracking-wide text-muted-foreground">
                <tr className="border-b border-border">
                  <th className="py-2 font-semibold">{tr('Godina')}</th>
                  <th className="py-2 text-right font-semibold">{tr('Očekivano neto')}</th>
                  <th className="py-2 text-right font-semibold">{tr('Stvarno neto')}</th>
                  <th className="py-2 text-right font-semibold">{tr('Odstupanje')}</th>
                </tr>
              </thead>
              <tbody>
                {expected.history.map((row) => (
                  <tr
                    key={row.year}
                    className={cn(
                      'border-b border-border/70 last:border-0',
                      row.year === year ? 'bg-accent/10' : undefined,
                    )}
                  >
                    <td className="py-2">{row.year}</td>
                    <td className="py-2 text-right font-mono">
                      {amountOrDash(row.expected_pessimistic_net_kg, formatKg)}
                    </td>
                    <td className="py-2 text-right font-mono">
                      {amountOrDash(row.actual_net_kg, formatKg)}
                    </td>
                    <td className="py-2 text-right font-mono">
                      {row.difference_percent.available && row.difference_percent.value != null
                        ? formatPercentValue(row.difference_percent.value)
                        : amountOrDash(row.difference_kg, formatKg)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}

function ExpectedYieldChart({ curve }: { curve: ExpectedYield['curve'] }) {
  const maxValue = Math.max(
    ...curve.flatMap((row) => [Number(row.pessimistic), Number(row.realistic), Number(row.optimistic)]),
    1,
  )

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-muted-foreground/50" /> {tr('Pesimistični')}
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-primary" /> {tr('Realistični')}
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-accent" /> {tr('Optimistični')}
        </span>
      </div>
      <div className="overflow-x-auto">
        <div className="flex h-44 min-w-[36rem] items-end gap-2 px-1">
          {curve.map((row) => {
            const pessimistic = (Number(row.pessimistic) / maxValue) * 100
            const realistic = (Number(row.realistic) / maxValue) * 100
            const optimistic = (Number(row.optimistic) / maxValue) * 100
            return (
              <div key={row.age_year} className="flex min-w-0 flex-1 flex-col items-center gap-2">
                <div className="flex h-32 w-full items-end justify-center gap-0.5">
                  <div
                    className="w-full max-w-[0.45rem] rounded-t bg-muted-foreground/40"
                    style={{ height: `${Math.max(pessimistic, Number(row.pessimistic) > 0 ? 4 : 2)}%` }}
                    title={`${tr('Pesimistični')}: ${row.pessimistic} kg`}
                  />
                  <div
                    className={cn(
                      'w-full max-w-[0.45rem] rounded-t',
                      row.is_current ? 'bg-primary' : 'bg-primary/70',
                    )}
                    style={{ height: `${Math.max(realistic, Number(row.realistic) > 0 ? 4 : 2)}%` }}
                    title={`${tr('Realistični')}: ${row.realistic} kg`}
                  />
                  <div
                    className="w-full max-w-[0.45rem] rounded-t bg-accent/80"
                    style={{ height: `${Math.max(optimistic, Number(row.optimistic) > 0 ? 4 : 2)}%` }}
                    title={`${tr('Optimistični')}: ${row.optimistic} kg`}
                  />
                </div>
                <span
                  className={cn(
                    'text-[10px] tabular-nums',
                    row.is_current ? 'font-semibold text-foreground' : 'text-muted-foreground',
                  )}
                >
                  {row.age_year}
                </span>
              </div>
            )
          })}
        </div>
      </div>
      <p className="text-xs text-muted-foreground">
        {tr('X: godina od sadnje · Y: kg u ljusci / stablo (bruto)')}
      </p>
    </div>
  )
}

function Kpi({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Card className="min-w-0">
      <CardHeader className="px-3 py-3 sm:px-4">
        <CardTitle className="leading-tight">{label}</CardTitle>
      </CardHeader>
      <CardContent className="px-3 py-3 sm:px-4">
        <p className="break-words text-lg font-semibold sm:text-xl">{value}</p>
        {hint ? (
          <p className="mt-1 truncate whitespace-nowrap text-xs text-muted-foreground" title={hint}>
            {hint}
          </p>
        ) : null}
      </CardContent>
    </Card>
  )
}

function Mini({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-sm font-semibold">{value}</p>
    </div>
  )
}

function CompareStat({
  label,
  previous,
  current,
  change,
  previousYear,
}: {
  label: string
  previous: string
  current: string
  change: ReportYearChange
  previousYear: number
}) {
  return (
    <div className="rounded-lg border border-border px-3 py-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-sm">
        {previousYear}: {previous}
      </p>
      <p className="text-sm font-semibold">{current}</p>
      <p className={cn('mt-1 text-xs', change.tone === 'positive' ? 'text-ok' : change.tone === 'negative' ? 'text-danger' : 'text-muted-foreground')}>
        {change.available && change.percent != null ? formatPercentValue(change.percent) : tr('Nema uporedive promene')}
      </p>
    </div>
  )
}

function amountOrDash(amount: ReportOptionalAmount, format: (value: string) => string) {
  if (!amount.available || amount.value == null) return '—'
  return format(amount.value)
}

function avgText(avg: ParcelProduction['quality_summary']['moisture']) {
  if (!avg.available || avg.value == null) return tr('Nije izračunato')
  return `${Number(avg.value).toLocaleString('sr-Latn-RS', { maximumFractionDigits: 1 })}%`
}

function parseRowSort(value: string | null): RowSort {
  if (value === 'high' || value === 'low') return value
  return 'number'
}

function parseTreeStatus(value: string | null): TreeStatusFilter {
  if (value === 'active' || value === 'removed' || value === 'replaced') return value
  return 'all'
}
