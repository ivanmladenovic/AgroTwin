import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { downloadCostsCsv, getCostSummary, listCosts } from '@/features/journal/api'
import { listParcels } from '@/features/orchard/api'
import { activityTarget, formatDate, formatMoney, formatNumber, formatWorkQuantities } from '@/shared/lib/format'
import { cn } from '@/shared/lib/utils'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'
import { Select } from '@/shared/ui/select'

export function CostSummaryPage() {
  const [parcelId, setParcelId] = useState('')
  const parcelsQuery = useQuery({ queryKey: ['parcels'], queryFn: listParcels })
  const summaryQuery = useQuery({
    queryKey: ['cost-summary', parcelId],
    queryFn: () => getCostSummary(parcelId || undefined),
  })
  const costsQuery = useQuery({
    queryKey: ['costs', parcelId],
    queryFn: () => listCosts(parcelId || undefined),
  })
  const summary = summaryQuery.data
  const costs = costsQuery.data ?? []

  return (
    <div className="w-full space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="kicker">Troškovi</p>
          <h1 className="mt-1 text-xl font-semibold sm:text-2xl">Pregled troškova voćnjaka</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Troškovi se unose u dnevniku aktivnosti, stavkom sa jedinicom EUR.
          </p>
        </div>
        <div className="flex w-full flex-wrap gap-2 sm:w-auto">
          <Button variant="outline" onClick={() => void downloadCostsCsv({ parcel_id: parcelId })}>
            Izvezi CSV
          </Button>
          <Link to="/journal">
            <Button variant="outline">Otvori dnevnik</Button>
          </Link>
        </div>
      </div>

      <div className="max-w-xs">
        <Select value={parcelId} onChange={(event) => setParcelId(event.target.value)}>
          <option value="">Sve parcele</option>
          {(parcelsQuery.data ?? []).map((parcel) => (
            <option key={parcel.id} value={parcel.id}>
              {parcel.name}
            </option>
          ))}
        </Select>
      </div>

      {summaryQuery.isLoading || !summary ? (
        <p className="text-sm text-muted-foreground">Učitavanje troškova…</p>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-5">
            <Metric label="Ukupni troškovi" value={formatMoney(summary.total_costs, summary.currency)} />
            <Metric label="Tekuća godina" value={formatMoney(summary.current_year_costs, summary.currency)} />
            <Metric label="Tekući mesec" value={formatMoney(summary.current_month_costs, summary.currency)} />
            <Metric
              label="Trošak po stablu"
              value={summary.cost_per_tree ? formatMoney(summary.cost_per_tree, summary.currency) : '—'}
              hint={`${formatNumber(summary.active_tree_count)} aktivnih stabala`}
            />
            <Metric
              label="Trošak po hektaru"
              value={summary.cost_per_hectare ? formatMoney(summary.cost_per_hectare, summary.currency) : '—'}
              hint={`${Number(summary.area_hectares).toFixed(2)} ha površine parcela`}
            />
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <Breakdown title="Po kategoriji" rows={summary.by_category} currency={summary.currency} />
            <Breakdown title="Po tipu aktivnosti" rows={summary.by_activity_type} currency={summary.currency} />
          </div>

          {(summary.by_year ?? []).length > 1 ? (
            <Card>
              <CardHeader>
                <CardTitle>Po godini, od sadnje</CardTitle>
              </CardHeader>
              <CardContent>
                <YearBars rows={summary.by_year} currency={summary.currency} currentYear={new Date().getFullYear()} />
              </CardContent>
            </Card>
          ) : null}

          <Card>
            <CardHeader>
              <CardTitle>Stavke iz dnevnika</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {costsQuery.isLoading ? (
                <p className="text-sm text-muted-foreground">Učitavanje stavki…</p>
              ) : costs.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  Nema evidentiranih troškova. Dodajte stavku sa jedinicom EUR u dnevniku aktivnosti.
                </p>
              ) : (
                costs.map((cost) => (
                  <Link
                    key={cost.id}
                    to={`/activities/${cost.activity_id}?returnTo=/costs`}
                    className="flex items-baseline justify-between gap-3 rounded-lg px-1 py-2 text-sm hover:bg-muted/60"
                  >
                    <div className="min-w-0">
                      <p>{cost.activity_title || cost.description}</p>
                      <p className="text-[11px] leading-4 text-muted-foreground">
                        {formatDate(cost.incurred_on)}
                        {cost.activity_type_name && cost.activity_type_name !== cost.activity_title
                          ? ` · ${cost.activity_type_name}`
                          : ''}
                        {' · '}
                        {activityTarget(cost)}
                      </p>
                      {formatWorkQuantities(cost.activity_line_items) ? (
                        <p className="mt-0.5 text-[11px] leading-4 text-muted-foreground">
                          {formatWorkQuantities(cost.activity_line_items)}
                        </p>
                      ) : null}
                    </div>
                    <span className="shrink-0 font-mono">{formatMoney(cost.amount, cost.currency)}</span>
                  </Link>
                ))
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}

function Metric({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Card className="min-w-0">
      <CardHeader className="px-3 py-3 sm:px-4">
        <CardTitle className="leading-tight">{label}</CardTitle>
      </CardHeader>
      <CardContent className="px-3 py-3 sm:px-4">
        <p className="break-words text-lg font-semibold sm:text-xl lg:text-2xl">{value}</p>
        {hint ? <p className="mt-1 text-xs text-muted-foreground">{hint}</p> : null}
      </CardContent>
    </Card>
  )
}

function Breakdown({
  title,
  rows,
  currency,
}: {
  title: string
  rows: Array<{ id: string; name: string; amount: string }>
  currency: string
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nema evidentiranih troškova.</p>
        ) : (
          rows.map((row) => (
            <div key={row.id} className="flex items-center justify-between text-sm">
              <span>{row.name}</span>
              <span className="font-mono">{formatMoney(row.amount, currency)}</span>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  )
}

function YearBars({
  rows,
  currency,
  currentYear,
}: {
  rows: Array<{ year: number; amount: string }>
  currency: string
  currentYear: number
}) {
  const maxYear = Math.max(...rows.map((row) => Number(row.amount)), 0)
  return (
    <div className="flex h-40 items-end gap-3">
      {rows.map((row) => {
        const amount = Number(row.amount)
        const height = maxYear > 0 ? Math.max((amount / maxYear) * 100, amount > 0 ? 8 : 2) : 2
        const isCurrent = row.year === currentYear
        return (
          <div key={row.year} className="flex min-w-0 flex-1 flex-col items-center gap-2">
            <p className="text-xs font-mono text-muted-foreground">{formatMoney(row.amount, currency)}</p>
            <div className="flex h-28 w-full items-end">
              <div
                className={cn(
                  'w-full rounded-t-md',
                  isCurrent ? 'bg-accent' : amount > 0 ? 'bg-primary/80' : 'bg-muted',
                )}
                style={{ height: `${height}%` }}
              />
            </div>
            <span className={cn('text-xs tabular-nums', isCurrent ? 'font-semibold text-accent' : 'text-muted-foreground')}>
              {row.year}
            </span>
          </div>
        )
      })}
    </div>
  )
}
