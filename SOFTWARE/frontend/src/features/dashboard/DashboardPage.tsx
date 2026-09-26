import { lazy, Suspense, useMemo, useRef, type ComponentType } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  ArrowRight,
  ChevronLeft,
  ChevronRight,
  MapPinned,
  MessageCircle,
  Plus,
  ShieldAlert,
  Sprout,
  Trees,
  Wallet,
} from 'lucide-react'

import { getDashboard } from '@/features/dashboard/api'
import { activityTarget, formatChartMoney, formatDate, formatMoney, formatNumber } from '@/shared/lib/format'
import { parcelCoordinates } from '@/shared/lib/maps'
import { cn } from '@/shared/lib/utils'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'
import type { DashboardOverview, DashboardParcel } from '@/shared/api/types'

const ParcelsMap = lazy(async () => {
  const module = await import('@/features/dashboard/ParcelsMap')
  return { default: module.ParcelsMap }
})

function monthLabel(month: number, width: 'short' | 'long' = 'short') {
  return new Intl.DateTimeFormat('sr-Latn-RS', { month: width }).format(new Date(2026, month - 1, 1))
}

export function DashboardPage() {
  const dashboardQuery = useQuery({ queryKey: ['dashboard'], queryFn: getDashboard })
  const data = dashboardQuery.data

  if (dashboardQuery.isError && !dashboardQuery.isFetching) {
    return (
      <div className="w-full">
        <p className="text-sm text-danger">Početna nije učitana. Osvežite stranicu.</p>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="w-full">
        <p className="text-sm text-muted-foreground">Učitavanje početne…</p>
      </div>
    )
  }

  return (
    <div className="w-full space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <h1 className="text-xl font-semibold sm:text-2xl">Početna</h1>
        <div className="flex flex-wrap items-center gap-2">
          <Link to="/activities/new">
            <Button>
              <Plus className="h-4 w-4" />
              Unesi aktivnost
            </Button>
          </Link>
          <Link to="/agronomist">
            <Button variant="outline">
              <MessageCircle className="h-4 w-4" />
              Pitaj agronoma
            </Button>
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        <StatCard
          label="Zasadi"
          value={formatNumber(data.stats.parcel_count)}
          detail={`${Number(data.stats.area_hectares).toFixed(2)} ha površine`}
          icon={MapPinned}
        />
        <StatCard
          label="Stabla"
          value={formatNumber(data.stats.active_tree_count)}
          detail="Aktivne sadnice"
          icon={Trees}
        />
        <StatCard
          label={`Troškovi ${data.stats.year}`}
          value={formatMoney(data.stats.year_costs, data.stats.currency)}
          detail={`${formatMoney(data.stats.month_costs, data.stats.currency)} ovaj mesec`}
          icon={Wallet}
          accent="accent"
        />
        <StatCard
          label="Otvoreni slučajevi"
          value={formatNumber(data.stats.open_health_cases)}
          detail="Zdravlje stabala"
          icon={ShieldAlert}
          accent={data.stats.open_health_cases > 0 ? 'warn' : 'ok'}
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-3 xl:items-stretch">
      <section className="flex min-h-[240px] flex-col xl:col-span-2 xl:min-h-[380px]">
          <div className="min-h-[240px] flex-1 overflow-hidden rounded-2xl border border-border bg-card sm:min-h-[360px]">
            <Suspense
              fallback={
                <div className="flex h-full min-h-[240px] items-center justify-center sm:min-h-[360px]">
                  <p className="text-sm text-muted-foreground">Učitavanje mape…</p>
                </div>
              }
            >
              <ParcelsMap className="h-full min-h-[240px] sm:min-h-[360px]" parcels={data.parcels} />
            </Suspense>
          </div>
        </section>

        <Card className="flex min-h-0 flex-col xl:min-h-[380px]">
          <CardHeader>
            <CardTitle>Brze akcije</CardTitle>
          </CardHeader>
          <CardContent className="grid flex-1 content-start gap-2">
            <QuickAction to="/activities/new" icon={Plus} label="Unesi aktivnost" hint="Radovi, prskanje, berba" />
            <QuickAction to="/health/new" icon={ShieldAlert} label="Prijavi problem" hint="Bolest, štetočina, stres" />
            <QuickAction to="/orchard/new" icon={Sprout} label="Novi zasad" hint="Nova parcela i raspored sadnje" />
            <QuickAction to="/agronomist" icon={MessageCircle} label="Pitaj agronoma" hint="Pitanje o voćnjaku" />
          </CardContent>
        </Card>
      </div>

      <ParcelSlider parcels={data.parcels} />

      <YearAnalytics data={data} />
    </div>
  )
}

function StatCard({
  label,
  value,
  detail,
  icon: Icon,
  accent = 'ok',
}: {
  label: string
  value: string
  detail: string
  icon: ComponentType<{ className?: string }>
  accent?: 'ok' | 'accent' | 'warn'
}) {
  const accentClass =
    accent === 'accent'
      ? 'bg-accent/10 text-accent'
      : accent === 'warn'
        ? 'bg-danger/10 text-danger'
        : 'bg-ok/10 text-ok'

  return (
    <article className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-muted-foreground">{label}</p>
          <p className="mt-2 break-words text-xl font-semibold tracking-tight sm:text-2xl">{value}</p>
          <p className="mt-2 text-xs font-medium text-muted-foreground">{detail}</p>
        </div>
        <div className={cn('rounded-xl p-3', accentClass)}>
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </article>
  )
}

function QuickAction({
  to,
  icon: Icon,
  label,
  hint,
}: {
  to: string
  icon: ComponentType<{ className?: string }>
  label: string
  hint: string
}) {
  return (
    <Link
      to={to}
      className="flex items-center gap-3 rounded-lg border border-border px-3 py-2.5 transition-colors hover:bg-muted/70"
    >
      <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
        <Icon className="h-4 w-4" />
      </span>
      <span className="min-w-0">
        <span className="block text-sm font-medium">{label}</span>
        <span className="block text-xs text-muted-foreground">{hint}</span>
      </span>
    </Link>
  )
}

function ParcelSlider({ parcels }: { parcels: DashboardParcel[] }) {
  const scrollRef = useRef<HTMLDivElement>(null)

  function scroll(direction: 'left' | 'right') {
    const container = scrollRef.current
    if (!container) return
    const cardWidth = container.querySelector('article')?.clientWidth ?? 288
    container.scrollBy({ left: direction === 'left' ? -(cardWidth + 16) : cardWidth + 16, behavior: 'smooth' })
  }

  return (
    <section className="rounded-xl border border-border bg-card p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold">Zasadi</h2>
          <p className="text-sm text-muted-foreground">Otvori zasad ili mapu parcele.</p>
        </div>
        {parcels.length > 1 ? (
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => scroll('left')}
              className="inline-flex h-11 w-11 items-center justify-center rounded-lg border border-border text-muted-foreground hover:bg-muted hover:text-foreground"
              aria-label="Prethodni zasadi"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={() => scroll('right')}
              className="inline-flex h-11 w-11 items-center justify-center rounded-lg border border-border text-muted-foreground hover:bg-muted hover:text-foreground"
              aria-label="Sledeći zasadi"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        ) : null}
      </div>

      {parcels.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border px-4 py-8 text-center">
          <p className="text-sm text-muted-foreground">Još nema zasada. Napravite prvu parcelu da otvorite pregled zasada.</p>
          <Link to="/orchard/new" className="mt-3 inline-flex">
            <Button size="sm">Nova parcela</Button>
          </Link>
        </div>
      ) : (
        <div
          ref={scrollRef}
          className="flex snap-x snap-mandatory gap-4 overflow-x-auto pb-1 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
        >
          {parcels.map((parcel) => (
            <ParcelCard key={parcel.id} parcel={parcel} />
          ))}
        </div>
      )}
    </section>
  )
}

function ParcelCard({ parcel }: { parcel: DashboardParcel }) {
  const located = Boolean(parcelCoordinates(parcel))
  return (
    <article className="flex w-[min(100%,18rem)] shrink-0 snap-start flex-col rounded-xl border border-border bg-background">
      <div className="border-b border-border p-4">
        {parcel.code === parcel.name ? null : <p className="kicker">{parcel.code}</p>}
        <h3 className={parcel.code === parcel.name ? 'text-lg font-semibold' : 'mt-1 text-lg font-semibold'}>{parcel.name}</h3>
        <p className="mt-2 text-xs text-muted-foreground">
          {located ? 'Lokacija je na mapi' : 'Google Maps link nije unet'}
        </p>
      </div>
      <div className="grid grid-cols-3 gap-2 p-4 text-sm">
        <Metric label="Stabla" value={formatNumber(parcel.tree_count)} />
        <Metric
          label="Površina"
          value={parcel.area_hectares ? `${Number(parcel.area_hectares).toFixed(2)} ha` : '—'}
        />
        <Metric label="Slučajevi" value={formatNumber(parcel.open_cases)} />
      </div>
      <div className="mt-auto flex items-center justify-between border-t border-border px-4 py-3 text-sm">
        <Link to={`/orchard/${parcel.id}`} className="inline-flex items-center gap-1 font-medium text-primary hover:underline">
          Otvori zasad
          <ArrowRight className="h-3.5 w-3.5" />
        </Link>
        {parcel.maps_url ? (
          <a href={parcel.maps_url} target="_blank" rel="noreferrer" className="text-xs font-medium text-muted-foreground hover:text-foreground">
            Google Maps
          </a>
        ) : (
          <Link to={`/orchard/${parcel.id}/edit`} className="text-xs font-medium text-muted-foreground hover:text-foreground">
            Dodaj lokaciju
          </Link>
        )}
      </div>
    </article>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-1 font-medium tabular-nums">{value}</p>
    </div>
  )
}

function CostKpi({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-lg border border-border bg-background px-3 py-3 sm:px-4">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-1 text-lg font-semibold tabular-nums sm:text-xl">{value}</p>
      {hint ? <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  )
}

function YearAnalytics({ data }: { data: DashboardOverview }) {
  const currency = data.stats.currency
  const year = data.stats.year
  const currentMonth = new Date().getMonth() + 1
  const lifetime = data.lifetime_by_year ?? []
  const maxYear = Math.max(...lifetime.map((row) => Number(row.amount)), 0)
  const maxMonth = useMemo(() => Math.max(...data.year_by_month.map((row) => Number(row.amount)), 0), [data.year_by_month])
  const maxCategory = Math.max(...data.year_by_category.map((row) => Number(row.amount)), 0)
  const lifetimeTotal = lifetime.reduce((sum, row) => sum + Number(row.amount || 0), 0)
  const plantingYear = lifetime[0]?.year

  return (
    <section className="rounded-xl border border-border bg-card p-5">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold">Troškovi</h2>
          <p className="text-sm text-muted-foreground">Mesec, tekuća godina i ukupno od sadnje.</p>
        </div>
        <Link to="/costs">
          <Button variant="outline" size="sm">
            Detaljni pregled
          </Button>
        </Link>
      </div>

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        <CostKpi label="Ovaj mesec" value={formatMoney(data.stats.month_costs, currency)} hint={monthLabel(currentMonth, 'long')} />
        <CostKpi label={`Godina ${year}`} value={formatMoney(data.stats.year_costs, currency)} />
        <CostKpi
          label="Od sadnje"
          value={formatMoney(lifetimeTotal, currency)}
          hint={plantingYear ? `od ${plantingYear}.` : undefined}
        />
      </div>

      {lifetime.length > 1 ? (
        <div className="mt-6">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Po godini</p>
          <div className="mt-3 flex items-end gap-3">
            {lifetime.map((row) => {
              const amount = Number(row.amount)
              const height = maxYear > 0 ? Math.max((amount / maxYear) * 100, amount > 0 ? 8 : 2) : 2
              const isCurrent = row.year === year
              return (
                <div key={row.year} className="flex min-w-0 flex-1 flex-col items-center">
                  <div className="flex h-28 w-full items-end">
                    <div
                      className={cn(
                        'w-full rounded-t-md',
                        isCurrent ? 'bg-accent' : amount > 0 ? 'bg-primary/80' : 'bg-muted',
                      )}
                      style={{ height: `${height}%` }}
                      title={`${row.year}: ${formatMoney(row.amount, currency)}`}
                    />
                  </div>
                  <span className={cn('mt-2 text-xs tabular-nums', isCurrent ? 'font-semibold text-accent' : 'text-muted-foreground')}>
                    {row.year}
                  </span>
                  <span
                    className={cn(
                      'mt-0.5 w-full text-center text-[11px] font-medium tabular-nums sm:text-xs',
                      isCurrent ? 'text-accent' : 'text-foreground',
                    )}
                  >
                    {formatChartMoney(row.amount, currency)}
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      ) : null}

      <div className="mt-6 grid gap-6 border-t border-border pt-5 lg:grid-cols-[1.4fr_0.8fr]">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Po mesecu · {year}</p>
          <div className="mt-3 flex items-end gap-1.5 sm:gap-2">
            {data.year_by_month.map((row) => {
              const amount = Number(row.amount)
              const height = maxMonth > 0 ? Math.max((amount / maxMonth) * 100, amount > 0 ? 6 : 2) : 2
              const isCurrent = row.month === currentMonth
              return (
                <div key={row.month} className="flex min-w-0 flex-1 flex-col items-center">
                  <div className="flex h-28 w-full items-end sm:h-32">
                    <div
                      className={cn(
                        'w-full rounded-t-md',
                        isCurrent ? 'bg-accent' : amount > 0 ? 'bg-primary/80' : 'bg-muted',
                      )}
                      style={{ height: `${height}%` }}
                      title={`${monthLabel(row.month)}: ${formatMoney(row.amount, currency)}`}
                    />
                  </div>
                  <span className={cn('mt-2 text-[10px] uppercase', isCurrent ? 'font-semibold text-accent' : 'text-muted-foreground')}>
                    {monthLabel(row.month).replace('.', '')}
                  </span>
                  <span
                    className={cn(
                      'mt-0.5 min-h-[1rem] w-full text-center text-[10px] font-medium tabular-nums',
                      isCurrent ? 'text-accent' : 'text-foreground',
                    )}
                  >
                    {amount > 0 ? formatChartMoney(row.amount, currency) : ''}
                  </span>
                </div>
              )
            })}
          </div>
        </div>

        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Po kategoriji · {year}</p>
          <div className="mt-3 space-y-3">
            {data.year_by_category.length === 0 ? (
              <p className="text-sm text-muted-foreground">Nema evidentiranih troškova ove godine.</p>
            ) : (
              data.year_by_category.map((row) => (
                <div key={row.id}>
                  <div className="mb-1 flex items-center justify-between gap-3 text-sm">
                    <span className="truncate">{row.name}</span>
                    <span className="shrink-0 font-medium tabular-nums">{formatChartMoney(row.amount, currency)}</span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full bg-primary"
                      style={{ width: `${maxCategory > 0 ? Math.max((Number(row.amount) / maxCategory) * 100, 4) : 0}%` }}
                    />
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {data.recent_activities.length > 0 ? (
        <div className="mt-6 border-t border-border pt-5">
          <div className="mb-3 flex items-center justify-between gap-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Poslednje aktivnosti</p>
            <Link to="/journal" className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline">
              Dnevnik
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
          <ul className="grid gap-2 md:grid-cols-2">
            {data.recent_activities.map((activity) => (
              <li key={activity.id}>
                <Link
                  to={`/activities/${activity.id}`}
                  className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2.5 text-sm hover:bg-muted/70"
                >
                  <span className="min-w-0">
                    <span className="block truncate font-medium">{activity.title}</span>
                    <span className="block text-xs text-muted-foreground">
                      {activityTarget(activity)} · {formatDate(activity.performed_on)}
                    </span>
                  </span>
                  <span className="shrink-0 font-mono text-xs">{formatMoney(activity.total_cost, activity.currency)}</span>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  )
}
