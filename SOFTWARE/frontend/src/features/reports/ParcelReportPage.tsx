import { useMemo, type ReactNode } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Printer } from 'lucide-react'

import { listParcels } from '@/features/orchard/api'
import { healthLabel } from '@/features/orchard/health'
import { getParcelAnnualReport } from '@/features/reports/api'
import { categoryLabel } from '@/features/health/labels'
import {
  formatDate,
  formatMoney,
  formatNumber,
  LOCALE,
  rowLabel,
} from '@/shared/lib/format'
import { cn } from '@/shared/lib/utils'
import type {
  ParcelAnnualReport,
  ReportAttentionTree,
  ReportKpi,
  ReportNamedAmount,
  ReportOptionalAmount,
  ReportYearChange,
} from '@/shared/api/types'
import { Button } from '@/shared/ui/button'
import { Label } from '@/shared/ui/label'
import { Select } from '@/shared/ui/select'

const UNAVAILABLE = 'Nije dostupno'

export function ParcelReportPage() {
  const { parcelId: routeParcelId } = useParams()
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const parcelsQuery = useQuery({ queryKey: ['parcels'], queryFn: listParcels })
  const parcels = parcelsQuery.data ?? []
  const selectedParcelId = routeParcelId || params.get('parcelId') || parcels[0]?.id || ''
  const requestedYear = Number(params.get('year') || '')
  const fallbackYear = new Date().getFullYear()
  const year = Number.isInteger(requestedYear) && requestedYear >= 1990 ? requestedYear : fallbackYear

  const reportQuery = useQuery({
    queryKey: ['parcel-report', selectedParcelId, year],
    queryFn: () => getParcelAnnualReport(selectedParcelId, year),
    enabled: Boolean(selectedParcelId),
  })
  const report = reportQuery.data
  const years = useMemo(() => {
    const collected = new Set(report?.parcel_summary.available_years ?? [])
    collected.add(year)
    collected.add(fallbackYear)
    return [...collected].sort((a, b) => a - b)
  }, [fallbackYear, report, year])

  function updateYear(nextYear: number) {
    const next = new URLSearchParams(params)
    next.set('year', String(nextYear))
    setParams(next, { replace: true })
  }

  function updateParcel(nextParcelId: string) {
    if (routeParcelId) {
      navigate(`/orchard/${nextParcelId}/report?year=${year}`)
      return
    }
    const next = new URLSearchParams(params)
    next.set('parcelId', nextParcelId)
    next.set('year', String(year))
    setParams(next, { replace: true })
  }

  function printReport() {
    const root = document.documentElement
    root.classList.add('printing-report')
    const cleanup = () => {
      root.classList.remove('printing-report')
      window.removeEventListener('afterprint', cleanup)
    }
    window.addEventListener('afterprint', cleanup)
    // Let layout expand before the browser captures pages.
    requestAnimationFrame(() => {
      window.print()
      // Safari sometimes skips afterprint; clear soon after dialog closes.
      window.setTimeout(cleanup, 1000)
    })
  }

  if (!selectedParcelId && !parcelsQuery.isLoading) {
    return (
      <div className="w-full">
        <p className="text-sm text-muted-foreground">Nema parcele za izveštaj. Prvo napravite zasad.</p>
      </div>
    )
  }

  return (
    <div className="w-full min-w-0 space-y-6 print:space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-4 print:hidden">
        <div>
          <p className="kicker">Izveštaj</p>
          <h1 className="mt-1 text-xl font-semibold sm:text-2xl">Godišnji izveštaj parcele</h1>
        </div>
        <Button type="button" variant="outline" onClick={printReport}>
          <Printer className="h-4 w-4" />
          Štampaj / PDF
        </Button>
      </div>

      <div className="grid gap-3 print:hidden sm:grid-cols-2 lg:grid-cols-[1fr_10rem_auto] lg:items-end">
        <div className="space-y-1.5">
          <Label>Parcela</Label>
          <Select value={selectedParcelId} onChange={(event) => updateParcel(event.target.value)}>
            {parcels.map((parcel) => (
              <option key={parcel.id} value={parcel.id}>
                {parcel.name}
              </option>
            ))}
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label>Godina</Label>
          <Select value={String(year)} onChange={(event) => updateYear(Number(event.target.value))}>
            {years.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </Select>
        </div>
        {report?.parcel_summary.comparison_available ? (
          <p className="text-sm text-muted-foreground lg:pb-2.5">
            Poređenje sa {report.parcel_summary.previous_year}.
          </p>
        ) : (
          <p className="text-sm text-muted-foreground lg:pb-2.5">Nema podataka za poređenje.</p>
        )}
      </div>

      {reportQuery.isLoading || !report ? (
        <p className="text-sm text-muted-foreground">Priprema izveštaja…</p>
      ) : reportQuery.isError ? (
        <p className="text-sm text-danger">Izveštaj nije učitan. Osvežite stranicu.</p>
      ) : (
        <ReportDocument report={report} />
      )}
    </div>
  )
}

function ReportDocument({ report }: { report: ParcelAnnualReport }) {
  const header = report.parcel_summary
  const health = report.health_summary
  const financial = report.financial_summary
  const problems = report.problem_summary
  const harvest = report.yield_summary
  const generated = formatLongDate(header.generated_on)
  const journalHref = `/journal?parcelId=${header.parcel_id}&view=list&date_from=${header.year}-01-01&date_to=${header.year}-12-31`
  const agendaHref = `/journal?parcelId=${header.parcel_id}`
  const orchardAttentionHref = `/orchard/${header.parcel_id}?health=attention`
  const healthHref = `/health?parcelId=${header.parcel_id}`
  const yieldRow = report.previous_year_comparison.find((row) => row.key === 'yield_kg')
  const yieldChange =
    yieldRow?.change.available && yieldRow.change.percent != null
      ? `${Number(yieldRow.change.percent) > 0 ? '+' : ''}${Number(yieldRow.change.percent).toLocaleString(LOCALE, { maximumFractionDigits: 1 })}%`
      : null

  return (
    <article className="report-sheet min-w-0 space-y-6 rounded-xl border border-border bg-card px-4 py-5 sm:space-y-8 sm:px-8 sm:py-8 print:space-y-6 print:rounded-none print:border-0 print:bg-white print:px-0 print:py-0">
      <header className="print-avoid border-b border-border pb-5 sm:pb-6">
        <p className="text-sm font-semibold tracking-[0.22em] text-primary uppercase">AgroTwin</p>
        <p className="mt-2 text-[11px] font-bold tracking-[0.18em] text-accent uppercase sm:mt-3 sm:tracking-[0.22em]">
          Godišnji izveštaj parcele
        </p>
        <h2 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">
          {header.farm_name ? `${header.farm_name} — ${header.parcel_name}` : header.parcel_name}
        </h2>
        <p className="mt-2 text-base text-muted-foreground sm:text-lg">
          {header.year}.
          {header.comparison_available ? ` · upoređeno sa ${header.previous_year}.` : ' · nema podataka za poređenje'}
        </p>
        <p className="mt-2 text-sm text-muted-foreground sm:mt-3">Generisano: {generated}</p>
      </header>

      <section className="print-avoid">
        <SectionTitle>Pregled godine</SectionTitle>
        <p className="mt-3 max-w-3xl text-sm leading-relaxed text-foreground">{report.executive_summary}</p>
        <div className="mt-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
          {report.kpis.map((kpi) => (
            <KpiCard key={kpi.key} kpi={kpi} previousYear={header.previous_year} currency={header.currency} />
          ))}
        </div>
      </section>

      <section className="print-avoid">
        <SectionTitle>Stanje parcele</SectionTitle>
        <HealthBar health={health} />
        <div className="mt-4 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4 lg:grid-cols-7">
          <MiniStat label="Ukupno" value={formatNumber(health.total_trees)} />
          <MiniStat label="Zdravo" value={formatNumber(health.healthy)} />
          <MiniStat label="Praćenje" value={formatNumber(health.monitoring)} />
          <MiniStat label="Problem" value={formatNumber(health.issue)} />
          <MiniStat label="Nepoznato" value={formatNumber(health.unknown)} />
          <MiniStat label="Uklonjeno" value={formatNumber(health.removed)} />
          <MiniStat label="Zamenjeno" value={formatNumber(health.replaced)} />
        </div>
        <div className="mt-6">
          <div className="flex flex-wrap items-end justify-between gap-2">
            <h3 className="text-sm font-semibold">Stabla koja zahtevaju pažnju</h3>
            <Link to={orchardAttentionHref} className="print-hidden shrink-0 text-sm font-medium text-primary hover:underline">
              Na mapi
            </Link>
          </div>
          {report.trees_requiring_attention.length === 0 ? (
            <p className="mt-3 text-sm text-muted-foreground">Nema stabala koja trenutno zahtevaju pažnju.</p>
          ) : (
            <AttentionTable trees={report.trees_requiring_attention} parcelId={header.parcel_id} />
          )}
        </div>
      </section>

      <section className="print-avoid">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <SectionTitle>Aktivnosti tokom godine</SectionTitle>
          <Link to={journalHref} className="print-hidden text-sm font-medium text-primary hover:underline">
            Otvori dnevnik
          </Link>
        </div>
        {report.activities_summary.by_type.length === 0 ? (
          <p className="mt-3 text-sm text-muted-foreground">Nema urađenih aktivnosti u {header.year}. godini.</p>
        ) : (
          <CountBars rows={report.activities_summary.by_type} />
        )}
        {report.activities_summary.timeline.length > 0 ? (
          <ol className="mt-5 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {report.activities_summary.timeline.map((item) => (
              <li
                key={`${item.month}-${item.title}`}
                className="rounded-lg border border-border bg-background px-3 py-2.5 sm:rounded-none sm:border-0 sm:border-l-2 sm:border-primary/30 sm:bg-transparent sm:px-0 sm:py-0 sm:pl-3"
              >
                <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                  {monthName(item.month)}
                </p>
                <p className="mt-0.5 text-sm font-medium">{item.activity_type_name}</p>
              </li>
            ))}
          </ol>
        ) : null}
      </section>

      <section className="print-avoid">
        <div className="flex items-end justify-between gap-3">
          <SectionTitle>Planirane aktivnosti</SectionTitle>
          <Link to={agendaHref} className="print-hidden text-sm font-medium text-primary hover:underline">
            Otvori agendu
          </Link>
        </div>
        {report.planned_activities.length === 0 ? (
          <p className="mt-3 text-sm text-muted-foreground">Nema predstojećih planiranih aktivnosti.</p>
        ) : (
          <ul className="mt-3 divide-y divide-border">
            {report.planned_activities.map((item) => (
              <li key={item.id} className="flex items-baseline justify-between gap-4 py-2.5 text-sm">
                <div>
                  <p className="font-medium">{item.title}</p>
                  <p className="text-xs text-muted-foreground">
                    {item.activity_type_name}
                    {item.row_number ? ` · ${rowLabel(item.row_number)}` : ''}
                    {item.tree_public_id ? ` · ${item.tree_public_id}` : ''}
                  </p>
                </div>
                <span className="shrink-0 tabular-nums text-muted-foreground">{formatDate(item.performed_on)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="print-avoid">
        <SectionTitle>Troškovi i finansije</SectionTitle>
        {!financial.recorded ? (
          <p className="mt-3 text-sm text-muted-foreground">Nema podataka o troškovima.</p>
        ) : (
          <>
            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              <FinanceStat
                label={`Ukupan trošak — ${header.year}.`}
                value={optionalMoney(financial.annual_cost, header.currency)}
              />
              <FinanceStat
                label={`${header.previous_year}.`}
                value={optionalMoney(financial.previous_year_cost, header.currency)}
              />
              <FinanceStat
                label="Od osnivanja zasada"
                value={optionalMoney(financial.historical_cost, header.currency)}
              />
            </div>
            {financial.previous_year_cost.available && financial.annual_cost.available ? (
              <p className="mt-3 text-sm text-muted-foreground">
                Promena:{' '}
                {formatChangeText(
                  changeFromValues(financial.previous_year_cost.value, financial.annual_cost.value, 'annual_cost'),
                  header.previous_year,
                )}
              </p>
            ) : (
              <p className="mt-3 text-sm text-muted-foreground">Nema podataka za poređenje.</p>
            )}
            <div className="mt-6 grid gap-6 lg:grid-cols-2">
              <div>
                <h3 className="text-sm font-semibold">Po kategoriji</h3>
                {financial.by_category.length === 0 ? (
                  <p className="mt-3 text-sm text-muted-foreground">Nema troškova po kategoriji.</p>
                ) : (
                  <AmountBars rows={financial.by_category} currency={header.currency} />
                )}
              </div>
              <div>
                <h3 className="text-sm font-semibold">Najveći troškovi po aktivnosti</h3>
                {financial.by_activity.length === 0 ? (
                  <p className="mt-3 text-sm text-muted-foreground">Nema troškova vezanih za aktivnosti.</p>
                ) : (
                  <AmountBars rows={financial.by_activity} currency={header.currency} />
                )}
              </div>
            </div>
            <div className="mt-6">
              <h3 className="text-sm font-semibold">Efikasnost</h3>
              <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
                <MiniStat label="Po hektaru" value={optionalMoney(financial.cost_per_hectare, header.currency)} />
                <MiniStat label="Po stablu" value={optionalMoney(financial.cost_per_tree, header.currency)} />
                <MiniStat label="Po kilogramu prinosa" value={optionalMoney(financial.cost_per_kg, header.currency)} />
              </div>
            </div>
          </>
        )}
      </section>

      <section className="print-avoid">
        <div className="flex items-end justify-between gap-3">
          <SectionTitle>Problemi tokom godine</SectionTitle>
          <Link to={healthHref} className="print-hidden text-sm font-medium text-primary hover:underline">
            Otvori zdravlje
          </Link>
        </div>
        {!problems.recorded || problems.total === 0 ? (
          <p className="mt-3 text-sm text-muted-foreground">Nema zabeleženih problema.</p>
        ) : (
          <>
            <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
              <MiniStat label="Ukupno" value={formatNumber(problems.total)} />
              <MiniStat label="Otvoreno" value={formatNumber(problems.open_count)} />
              <MiniStat label="Praćenje" value={formatNumber(problems.monitoring_count)} />
              <MiniStat label="Rešeno" value={formatNumber(problems.resolved_count)} />
            </div>
            <h3 className="mt-5 text-sm font-semibold">Najčešći problemi</h3>
            <ul className="mt-2 space-y-1.5 text-sm">
              {problems.by_category.map((item, index) => (
                <li key={item.slug ?? item.name} className="flex justify-between gap-3">
                  <span>
                    {index + 1}. {categoryLabel(item.slug ?? item.name)}
                  </span>
                  <span className="tabular-nums text-muted-foreground">{item.count}</span>
                </li>
              ))}
            </ul>
            <h3 className="mt-5 text-sm font-semibold">Problemi po redu</h3>
            {problems.by_row.length === 0 ? (
              <p className="mt-2 text-sm text-muted-foreground">Nema slučajeva vezanih za konkretan red.</p>
            ) : (
              <CountBars
                rows={problems.by_row.map((row) => ({
                  id: row.row_id,
                  name: rowLabel(row.row_number),
                  slug: String(row.row_number),
                  count: row.count,
                }))}
                hrefFor={(row) => `/orchard/${header.parcel_id}?row=${row.slug}`}
              />
            )}
          </>
        )}
      </section>

      <section className="print-avoid">
        <div className="flex items-end justify-between gap-3">
          <SectionTitle>Stabla za kontrolu</SectionTitle>
          <Link to={orchardAttentionHref} className="print-hidden shrink-0 text-sm font-medium text-primary hover:underline">
            Na mapi
          </Link>
        </div>
        {report.trees_requiring_control.length === 0 ? (
          <p className="mt-3 text-sm text-muted-foreground">Nema stabala za kontrolu.</p>
        ) : (
          <AttentionTable trees={report.trees_requiring_control} parcelId={header.parcel_id} showReason />
        )}
      </section>

      <section className="print-avoid">
        <div className="flex items-end justify-between gap-3">
          <SectionTitle>Proizvodnja</SectionTitle>
          <Link
            to={`/orchard/${header.parcel_id}/production?year=${header.year}`}
            className="print-hidden text-sm font-medium text-primary hover:underline"
          >
            Pogledaj proizvodnju
          </Link>
        </div>
        {!harvest.recorded ? (
          <p className="mt-3 text-sm text-muted-foreground">Prinos nije zabeležen.</p>
        ) : (
          <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <MiniStat label="Ukupan prinos" value={formatKg(harvest.total_kg)} />
            <MiniStat label="Po hektaru" value={harvest.per_hectare.available ? `${formatKg(harvest.per_hectare.value)}/ha` : UNAVAILABLE} />
            <MiniStat label="Po stablu" value={harvest.per_tree.available ? `${formatKg(harvest.per_tree.value)}/stablo` : UNAVAILABLE} />
            <MiniStat
              label="Berbe"
              value={harvest.harvest_events != null ? formatNumber(harvest.harvest_events) : UNAVAILABLE}
            />
            <MiniStat
              label="Prva berba"
              value={harvest.first_harvest_date ? formatDate(harvest.first_harvest_date) : UNAVAILABLE}
            />
            <MiniStat
              label="Poslednja berba"
              value={harvest.last_harvest_date ? formatDate(harvest.last_harvest_date) : UNAVAILABLE}
            />
            {yieldChange ? (
              <MiniStat label={`Naspram ${header.previous_year}.`} value={yieldChange} />
            ) : null}
          </div>
        )}
      </section>

      <section className="print-avoid">
        <SectionTitle>
          {header.year}. naspram {header.previous_year}.
        </SectionTitle>
        {!header.comparison_available || report.previous_year_comparison.length === 0 ? (
          <p className="mt-3 text-sm text-muted-foreground">Nema podataka za poređenje.</p>
        ) : (
          <div className="print-scroll-x mt-3 overflow-x-auto rounded-xl border border-border sm:overflow-visible sm:rounded-none sm:border-0">
            <table className="w-full min-w-[28rem] text-left text-sm print:min-w-0 sm:min-w-[32rem]">
              <thead className="text-xs uppercase tracking-wide text-muted-foreground">
                <tr className="border-b border-border">
                  <th className="px-3 py-2.5 font-semibold sm:px-0 sm:py-2">Pokazatelj</th>
                  <th className="px-3 py-2.5 font-semibold sm:px-0 sm:py-2">{header.previous_year}.</th>
                  <th className="px-3 py-2.5 font-semibold sm:px-0 sm:py-2">{header.year}.</th>
                  <th className="px-3 py-2.5 font-semibold sm:px-0 sm:py-2">Promena</th>
                </tr>
              </thead>
              <tbody>
                {report.previous_year_comparison.map((row) => (
                  <tr key={row.key} className="border-b border-border/70 last:border-0">
                    <td className="px-3 py-2.5 sm:px-0">{row.label}</td>
                    <td className="px-3 py-2.5 tabular-nums sm:px-0">{formatKpiValue(row.kind, row.previous, header.currency)}</td>
                    <td className="px-3 py-2.5 tabular-nums sm:px-0">{formatKpiValue(row.kind, row.current, header.currency)}</td>
                    <td className="px-3 py-2.5 sm:px-0">{formatChangeText(row.change, header.previous_year)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="print-avoid">
        <SectionTitle>Tok godine — mesečni troškovi</SectionTitle>
        <MonthBars months={report.yearly_trend.months} currency={header.currency} recorded={financial.recorded} />
      </section>

      <footer className="border-t border-border pt-5 text-xs text-muted-foreground">
        <p>AgroTwin · {header.parcel_name} · {header.year}.</p>
        <p className="mt-1">Generisano {generated} Izveštaj je sažetak postojećih evidencija, bez predikcija.</p>
      </footer>
    </article>
  )
}

function SectionTitle({ children }: { children: ReactNode }) {
  return <h2 className="text-xs font-bold tracking-[0.18em] text-accent uppercase">{children}</h2>
}

function KpiCard({
  kpi,
  previousYear,
  currency,
}: {
  kpi: ReportKpi
  previousYear: number
  currency: string
}) {
  return (
    <article className="print-avoid rounded-xl border border-border bg-background px-3 py-3 sm:px-4 sm:py-4">
      <p className="truncate text-[10px] font-semibold uppercase tracking-wide text-muted-foreground sm:text-[11px]">
        {kpi.label}
      </p>
      <p className="mt-1.5 text-xl font-semibold tracking-tight tabular-nums sm:mt-2 sm:text-2xl">
        {kpi.available ? formatKpiValue(kpi.kind, kpi.value, currency) : UNAVAILABLE}
      </p>
      {kpi.change.available ? <p className="mt-1.5 text-xs sm:mt-2">{formatChangeText(kpi.change, previousYear)}</p> : null}
    </article>
  )
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border bg-background px-3 py-2.5 sm:py-3">
      <p className="truncate text-[10px] font-semibold uppercase tracking-wide text-muted-foreground sm:text-[11px]">
        {label}
      </p>
      <p className="mt-1 truncate text-sm font-semibold tabular-nums" title={value}>
        {value}
      </p>
    </div>
  )
}

function FinanceStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border bg-background px-4 py-3.5 sm:py-4">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-2 text-lg font-semibold tabular-nums sm:text-xl">{value}</p>
    </div>
  )
}

function HealthBar({ health }: { health: ParcelAnnualReport['health_summary'] }) {
  const total = Math.max(health.total_trees, 1)
  const parts = [
    { key: 'healthy', value: health.healthy, className: 'bg-health-healthy' },
    { key: 'monitoring', value: health.monitoring, className: 'bg-health-monitoring' },
    { key: 'issue', value: health.issue, className: 'bg-health-issue' },
    { key: 'unknown', value: health.unknown, className: 'bg-health-unknown' },
  ]
  return (
    <div className="mt-4 flex h-2.5 overflow-hidden rounded-full bg-muted sm:h-3">
      {parts.map((part) =>
        part.value > 0 ? (
          <div key={part.key} className={part.className} style={{ width: `${(part.value / total) * 100}%` }} />
        ) : null,
      )}
    </div>
  )
}

function AttentionTable({
  trees,
  parcelId,
  showReason = false,
}: {
  trees: ReportAttentionTree[]
  parcelId: string
  showReason?: boolean
}) {
  return (
    <>
      <ul className="mt-3 space-y-2 print:hidden sm:hidden">
        {trees.map((tree) => {
          const status = showReason ? tree.reason : healthLabel(tree.health_status)
          const lastCheck = tree.last_check_on
            ? `${formatDate(tree.last_check_on)}${tree.days_since_check != null ? ` · pre ${tree.days_since_check}d` : ''}`
            : 'Bez pregleda'
          return (
            <li key={tree.tree_id} className="rounded-xl border border-border bg-background px-3 py-2.5">
              <div className="flex items-start justify-between gap-2">
                <Link
                  to={`/orchard/${parcelId}/trees/${tree.tree_id}`}
                  className="font-mono text-sm font-semibold text-primary hover:underline"
                >
                  {tree.public_id}
                </Link>
                <span
                  className={cn(
                    'shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide',
                    tree.health_status === 'issue'
                      ? 'bg-danger/10 text-danger'
                      : tree.health_status === 'monitoring'
                        ? 'bg-accent/15 text-accent'
                        : 'bg-muted text-muted-foreground',
                  )}
                >
                  {status}
                </span>
              </div>
              <p className="mt-1.5 truncate text-xs text-muted-foreground">
                <Link to={`/orchard/${parcelId}?row=${tree.row_number}`} className="hover:underline">
                  {rowLabel(tree.row_number)}
                </Link>
                <span aria-hidden> · </span>
                <span>{lastCheck}</span>
              </p>
            </li>
          )
        })}
      </ul>

      <div className="print-scroll-x mt-3 hidden overflow-x-auto print:block sm:block">
        <table className="w-full min-w-0 text-left text-sm">
          <thead className="text-xs uppercase tracking-wide text-muted-foreground">
            <tr className="border-b border-border">
              <th className="py-2 font-semibold">Stablo</th>
              <th className="py-2 font-semibold">Red</th>
              <th className="py-2 font-semibold">{showReason ? 'Razlog' : 'Status'}</th>
              <th className="py-2 font-semibold">Poslednji pregled</th>
            </tr>
          </thead>
          <tbody>
            {trees.map((tree) => (
              <tr key={tree.tree_id} className="border-b border-border/70">
                <td className="py-2.5">
                  <Link to={`/orchard/${parcelId}/trees/${tree.tree_id}`} className="font-medium text-primary hover:underline">
                    {tree.public_id}
                  </Link>
                </td>
                <td className="py-2.5">
                  <Link to={`/orchard/${parcelId}?row=${tree.row_number}`} className="hover:underline">
                    {rowLabel(tree.row_number)}
                  </Link>
                </td>
                <td className="py-2.5">{showReason ? tree.reason : healthLabel(tree.health_status)}</td>
                <td className="py-2.5 text-muted-foreground">
                  {tree.last_check_on
                    ? `${formatDate(tree.last_check_on)}${tree.days_since_check != null ? ` · pre ${tree.days_since_check} dana` : ''}`
                    : UNAVAILABLE}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

function CountBars({
  rows,
  hrefFor,
}: {
  rows: Array<{ id?: string | null; name: string; slug?: string | null; count: number }>
  hrefFor?: (row: { name: string; slug?: string | null }) => string
}) {
  const max = Math.max(...rows.map((row) => row.count), 0)
  return (
    <div className="mt-4 space-y-3">
      {rows.map((row) => {
        const label = <span className="truncate">{row.name}</span>
        return (
          <div key={row.id ?? row.slug ?? row.name} className="min-w-0">
            <div className="mb-1.5 flex items-center justify-between gap-3 text-sm">
              {hrefFor ? (
                <Link to={hrefFor(row)} className="min-w-0 truncate font-medium text-primary hover:underline">
                  {label}
                </Link>
              ) : (
                <span className="min-w-0 truncate">{row.name}</span>
              )}
              <span className="shrink-0 tabular-nums text-muted-foreground">{formatNumber(row.count)}</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-muted">
              <div
                className="h-full max-w-full rounded-full bg-primary"
                style={{ width: `${max > 0 ? Math.max((row.count / max) * 100, 4) : 0}%` }}
              />
            </div>
          </div>
        )
      })}
    </div>
  )
}

function AmountBars({ rows, currency }: { rows: ReportNamedAmount[]; currency: string }) {
  const max = Math.max(...rows.map((row) => Number(row.amount)), 0)
  return (
    <div className="mt-4 space-y-3">
      {rows.map((row) => (
        <div key={row.id ?? row.slug ?? row.name} className="min-w-0">
          <div className="mb-1.5 flex items-center justify-between gap-3 text-sm">
            <span className="min-w-0 truncate">{row.name}</span>
            <span className="shrink-0 tabular-nums text-muted-foreground">{formatMoney(row.amount, currency)}</span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full max-w-full rounded-full bg-primary"
              style={{ width: `${max > 0 ? Math.max((Number(row.amount) / max) * 100, 4) : 0}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  )
}

function MonthBars({
  months,
  currency,
  recorded,
}: {
  months: ParcelAnnualReport['yearly_trend']['months']
  currency: string
  recorded: boolean
}) {
  if (!recorded) {
    return <p className="mt-3 text-sm text-muted-foreground">Nema podataka o troškovima.</p>
  }
  const max = Math.max(...months.map((row) => Number(row.amount)), 0)
  return (
    <div className="print-scroll-x mt-4 -mx-1 overflow-x-auto overscroll-x-contain px-1 pb-1 print:mx-0 print:overflow-visible print:px-0 print:pb-0">
      <div className="flex min-w-[36rem] items-end gap-1.5 print:min-w-0 print:w-full sm:min-w-0 sm:w-full">
        {months.map((row) => {
          const amount = Number(row.amount)
          const height = max > 0 ? Math.max((amount / max) * 100, amount > 0 ? 8 : 2) : 2
          return (
            <div
              key={row.month}
              className="print-chart-col flex w-9 shrink-0 flex-col items-center gap-1.5 print:w-auto print:min-w-0 print:flex-1 print:shrink sm:w-auto sm:min-w-0 sm:flex-1"
            >
              <div className="flex h-24 w-full items-end">
                <div
                  className={cn('w-full rounded-t-md', amount > 0 ? 'bg-primary/80' : 'bg-muted')}
                  style={{ height: `${height}%` }}
                  title={`${monthName(row.month)}: ${formatMoney(row.amount, currency)}`}
                />
              </div>
              <span className="text-[9px] uppercase leading-none text-muted-foreground print:text-[8px] sm:text-[10px]">
                {monthName(row.month).slice(0, 3)}
              </span>
              <span className="hidden text-[8px] tabular-nums text-muted-foreground print:block">
                {amount > 0 ? formatChartAmount(amount) : '—'}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function formatChartAmount(amount: number) {
  if (amount >= 10000) return `${formatNumber(Math.round(amount / 1000))}k`
  if (amount >= 1000) return `${formatNumber(Math.round(amount / 100) / 10)}k`
  return formatNumber(Math.round(amount))
}

function formatKpiValue(kind: ReportKpi['kind'], value: string | number | null, currency: string) {
  if (value === null || value === undefined) return UNAVAILABLE
  if (kind === 'money') return formatMoney(value, currency)
  if (kind === 'mass') return formatKg(value)
  return formatNumber(Number(value))
}

function optionalMoney(amount: ReportOptionalAmount, currency: string) {
  if (!amount.available || amount.value === null) return UNAVAILABLE
  return formatMoney(amount.value, currency)
}

function formatKg(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === '') return UNAVAILABLE
  const numeric = Number(value)
  if (Number.isNaN(numeric)) return UNAVAILABLE
  return `${numeric.toLocaleString(LOCALE, { maximumFractionDigits: 2 })} kg`
}

function formatChangeText(change: ReportYearChange, previousYear: number) {
  if (!change.available) {
    return <span className="text-muted-foreground">Nema podataka za poređenje</span>
  }
  const arrow = change.direction === 'up' ? '↑' : change.direction === 'down' ? '↓' : '→'
  const verb = change.direction === 'up' ? 'povećano' : change.direction === 'down' ? 'smanjeno' : 'bez promene'
  const percent = change.percent === null ? verb : formatPercent(change.percent)
  return (
    <span className={cn(toneClass(change.tone))}>
      {arrow} {percent} vs {previousYear}. · {verb}
    </span>
  )
}

function formatPercent(value: string) {
  const numeric = Number(value)
  if (Number.isNaN(numeric)) return value
  const prefix = numeric > 0 ? '+' : ''
  return `${prefix}${numeric.toLocaleString(LOCALE, { maximumFractionDigits: 1 })}%`
}

function toneClass(tone: ReportYearChange['tone']) {
  if (tone === 'positive') return 'text-ok'
  if (tone === 'negative') return 'text-danger'
  return 'text-muted-foreground'
}

function changeFromValues(previous: string | null, current: string | null, key: string): ReportYearChange {
  if (previous === null || current === null) {
    return { available: false, previous: null, percent: null, direction: null, tone: null }
  }
  const prev = Number(previous)
  const curr = Number(current)
  const direction = curr > prev ? 'up' : curr < prev ? 'down' : 'unchanged'
  const percent = prev === 0 ? null : (((curr - prev) / prev) * 100).toFixed(1)
  const tone = key === 'annual_cost' ? 'neutral' : direction === 'unchanged' ? 'neutral' : 'neutral'
  return {
    available: true,
    previous,
    percent,
    direction,
    tone,
  }
}

function monthName(month: number) {
  return new Intl.DateTimeFormat(LOCALE, { month: 'long' }).format(new Date(2026, month - 1, 1))
}

function formatLongDate(value: string) {
  const date = new Date(`${value}T00:00:00`)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat(LOCALE, { day: 'numeric', month: 'long', year: 'numeric' }).format(date)
}
