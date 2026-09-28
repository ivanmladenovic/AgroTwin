import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'

import { createSubsidy, deleteSubsidy, downloadCostsCsv, getCostSummary, listCosts, listSubsidies } from '@/features/journal/api'
import { todayKey } from '@/features/journal/calendar'
import { listParcels } from '@/features/orchard/api'
import type { Subsidy } from '@/shared/api/types'
import { activityTarget, formatDate, formatMoney, formatNumber, formatWorkQuantities } from '@/shared/lib/format'
import { cn } from '@/shared/lib/utils'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { Select } from '@/shared/ui/select'
import { Textarea } from '@/shared/ui/textarea'

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
  const subsidiesQuery = useQuery({
    queryKey: ['subsidies', parcelId],
    queryFn: () => listSubsidies(parcelId || undefined),
  })
  const summary = summaryQuery.data
  const costs = costsQuery.data ?? []
  const subsidies = subsidiesQuery.data ?? []

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
          <div className="grid grid-cols-2 gap-2 sm:gap-3">
            <Metric label="Ukupni troškovi" value={formatMoney(summary.total_costs, summary.currency)} />
            <Metric label="Tekuća godina" value={formatMoney(summary.current_year_costs, summary.currency)} />
            <Metric label="Tekući mesec" value={formatMoney(summary.current_month_costs, summary.currency)} />
            <Metric
              label="Dobijeno kroz subvencije"
              value={formatMoney(summary.total_subsidies, summary.currency)}
              hint={
                summary.subsidy_percent_of_costs
                  ? `${formatShare(summary.subsidy_percent_of_costs)} ukupnog troška`
                  : 'Nema pokrivenosti dok nema evidentiranih troškova'
              }
            />
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

          <SubsidySection
            subsidies={subsidies}
            loading={subsidiesQuery.isLoading}
            parcelId={parcelId}
            parcels={parcelsQuery.data ?? []}
            currency={summary.currency}
          />

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
      <CardHeader className="px-2.5 py-2.5 sm:px-4 sm:py-3">
        <CardTitle className="text-[11px] leading-tight sm:text-sm">{label}</CardTitle>
      </CardHeader>
      <CardContent className="px-2.5 py-2.5 sm:px-4 sm:py-3">
        <p className="break-words text-base font-semibold tabular-nums sm:text-xl lg:text-2xl">{value}</p>
        {hint ? (
          <p className="mt-1 truncate whitespace-nowrap text-[10px] text-muted-foreground sm:text-xs" title={hint}>
            {hint}
          </p>
        ) : null}
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

function formatShare(value: string | number) {
  return `${Number(value).toLocaleString('sr-RS', { maximumFractionDigits: 1 })}%`
}

function SubsidySection({
  subsidies,
  loading,
  parcelId,
  parcels,
  currency,
}: {
  subsidies: Subsidy[]
  loading: boolean
  parcelId: string
  parcels: Array<{ id: string; name: string }>
  currency: string
}) {
  const [formOpen, setFormOpen] = useState(false)
  const queryClient = useQueryClient()
  const remove = useMutation({
    mutationFn: deleteSubsidy,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['subsidies'] })
      await queryClient.invalidateQueries({ queryKey: ['cost-summary'] })
    },
  })

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-3 space-y-0">
        <CardTitle>Sredstva dobijena kroz subvencije</CardTitle>
        <Button type="button" variant="outline" size="sm" onClick={() => setFormOpen((open) => !open)}>
          {formOpen ? 'Zatvori' : 'Unesi subvenciju'}
        </Button>
      </CardHeader>
      <CardContent className="space-y-4">
        {formOpen ? (
          <SubsidyForm
            defaultParcelId={parcelId}
            parcels={parcels}
            onDone={() => setFormOpen(false)}
          />
        ) : null}
        {loading ? (
          <p className="text-sm text-muted-foreground">Učitavanje subvencija…</p>
        ) : subsidies.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Nema evidentiranih subvencija. Unesite na šta se odnosila podrška, ukupni trošak i dobijeni iznos.
          </p>
        ) : (
          <div className="space-y-2">
            {subsidies.map((item) => (
              <div
                key={item.id}
                className="flex items-start justify-between gap-3 rounded-lg border border-border/60 px-3 py-2 text-sm"
              >
                <div className="min-w-0">
                  <p className="font-medium">{item.title}</p>
                  <p className="text-[11px] leading-4 text-muted-foreground">
                    {formatDate(item.received_on)}
                    {item.parcel_name ? ` · ${item.parcel_name}` : ' · Cela plantaža'}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Ukupni trošak {formatMoney(item.total_cost, currency)} · dobijeno {formatMoney(item.subsidy_amount, currency)}
                    {item.subsidy_percent ? ` (${formatShare(item.subsidy_percent)} troška)` : ''}
                  </p>
                  {item.notes ? <p className="mt-1 text-xs text-muted-foreground">{item.notes}</p> : null}
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="shrink-0 text-destructive"
                  disabled={remove.isPending}
                  onClick={() => {
                    if (window.confirm('Obrisati ovu subvenciju?')) remove.mutate(item.id)
                  }}
                >
                  Obriši
                </Button>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function SubsidyForm({
  defaultParcelId,
  parcels,
  onDone,
}: {
  defaultParcelId: string
  parcels: Array<{ id: string; name: string }>
  onDone: () => void
}) {
  const queryClient = useQueryClient()
  const [title, setTitle] = useState('')
  const [totalCost, setTotalCost] = useState('')
  const [subsidyAmount, setSubsidyAmount] = useState('')
  const [receivedOn, setReceivedOn] = useState(todayKey())
  const [parcelId, setParcelId] = useState(defaultParcelId)
  const [notes, setNotes] = useState('')
  const create = useMutation({
    mutationFn: createSubsidy,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['subsidies'] })
      await queryClient.invalidateQueries({ queryKey: ['cost-summary'] })
      onDone()
    },
  })

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    const cost = Number(totalCost.replace(',', '.'))
    const amount = Number(subsidyAmount.replace(',', '.'))
    if (!title.trim() || !Number.isFinite(cost) || cost <= 0 || !Number.isFinite(amount) || amount < 0) return
    create.mutate({
      title: title.trim(),
      total_cost: cost,
      subsidy_amount: amount,
      received_on: receivedOn,
      parcel_id: parcelId || null,
      notes: notes.trim() || null,
    })
  }

  return (
    <form onSubmit={onSubmit} className="space-y-3 rounded-lg border border-border/60 p-3">
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5 sm:col-span-2">
          <Label htmlFor="subsidy-title">Na šta se odnosilo</Label>
          <Input
            id="subsidy-title"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="npr. Sistem za navodnjavanje"
            required
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="subsidy-total">Ukupni trošak (EUR)</Label>
          <Input
            id="subsidy-total"
            inputMode="decimal"
            value={totalCost}
            onChange={(event) => setTotalCost(event.target.value)}
            required
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="subsidy-amount">Dobijeni iznos (EUR)</Label>
          <Input
            id="subsidy-amount"
            inputMode="decimal"
            value={subsidyAmount}
            onChange={(event) => setSubsidyAmount(event.target.value)}
            required
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="subsidy-date">Datum prijema</Label>
          <Input
            id="subsidy-date"
            type="date"
            value={receivedOn}
            onChange={(event) => setReceivedOn(event.target.value)}
            required
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="subsidy-parcel">Parcela (opciono)</Label>
          <Select id="subsidy-parcel" value={parcelId} onChange={(event) => setParcelId(event.target.value)}>
            <option value="">Cela plantaža</option>
            {parcels.map((parcel) => (
              <option key={parcel.id} value={parcel.id}>
                {parcel.name}
              </option>
            ))}
          </Select>
        </div>
        <div className="space-y-1.5 sm:col-span-2">
          <Label htmlFor="subsidy-notes">Napomena</Label>
          <Textarea
            id="subsidy-notes"
            rows={2}
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
          />
        </div>
      </div>
      {create.isError ? (
        <p className="text-sm text-destructive">
          {create.error instanceof Error ? create.error.message : 'Unos nije uspeo.'}
        </p>
      ) : null}
      <Button type="submit" disabled={create.isPending}>
        {create.isPending ? 'Čuvanje…' : 'Sačuvaj subvenciju'}
      </Button>
    </form>
  )
}
