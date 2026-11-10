import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { Printer } from 'lucide-react'

import {
  createEnterpriseAggregateReport,
  downloadEnterpriseAlertCsv,
  listEnterpriseParcels,
} from '@/features/enterprise/api'
import { useEnterprise } from '@/features/enterprise/EnterpriseContext'
import { formatDate, formatNumber, LOCALE } from '@/shared/lib/format'
import { BrandLogo } from '@/shared/ui/brand-logo'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Select } from '@/shared/ui/select'
import type { EnterpriseAggregateReport } from '@/shared/api/types'

import { tr } from '@/shared/i18n/i18n'
export function EnterpriseReportsPage() {
  useTranslation()
  const { organizationId, organization } = useEnterprise()
  const yearNow = new Date().getFullYear()
  const [year, setYear] = useState(String(yearNow))
  const [selected, setSelected] = useState<Record<string, boolean>>({})
  const [initializedSelection, setInitializedSelection] = useState(false)
  const [csvFrom, setCsvFrom] = useState('')
  const [csvTo, setCsvTo] = useState('')
  const [csvFarm, setCsvFarm] = useState('')
  const [csvParcel, setCsvParcel] = useState('')
  const [csvSeverity, setCsvSeverity] = useState('')
  const [csvStatus, setCsvStatus] = useState('')
  const [csvError, setCsvError] = useState<string | null>(null)
  const [csvBusy, setCsvBusy] = useState(false)

  const parcelsQuery = useQuery({
    queryKey: ['enterprise-parcels', organizationId],
    queryFn: () => listEnterpriseParcels(organizationId),
  })

  const parcels = parcelsQuery.data ?? []
  const selectedIds = useMemo(
    () => parcels.filter((p) => selected[p.parcel_id]).map((p) => p.parcel_id),
    [parcels, selected],
  )
  const seasonYear = Number(year) || yearNow

  useEffect(() => {
    if (initializedSelection || parcels.length === 0) return
    const next: Record<string, boolean> = {}
    for (const parcel of parcels) next[parcel.parcel_id] = true
    setSelected(next)
    setInitializedSelection(true)
  }, [parcels, initializedSelection])

  const reportQuery = useQuery({
    queryKey: ['enterprise-aggregate-report', organizationId, seasonYear, selectedIds],
    queryFn: () =>
      createEnterpriseAggregateReport(organizationId, {
        parcel_ids: selectedIds,
        year: seasonYear,
      }),
    enabled: initializedSelection && selectedIds.length > 0,
  })

  const report = reportQuery.data ?? null

  function toggleAll(on: boolean) {
    const next: Record<string, boolean> = {}
    for (const parcel of parcels) next[parcel.parcel_id] = on
    setSelected(next)
  }

  function printReport() {
    const root = document.documentElement
    root.classList.add('printing-report')
    const cleanup = () => {
      root.classList.remove('printing-report')
      window.removeEventListener('afterprint', cleanup)
    }
    window.addEventListener('afterprint', cleanup)
    requestAnimationFrame(() => {
      window.print()
      window.setTimeout(cleanup, 1000)
    })
  }

  const supplierGroups = useMemo(() => {
    const map = new Map<string, { label: string; parcels: typeof parcels }>()
    for (const parcel of parcels) {
      const key = parcel.farm_id
      const label = parcel.producer_display_name || parcel.farm_name
      const existing = map.get(key)
      if (existing) existing.parcels.push(parcel)
      else map.set(key, { label, parcels: [parcel] })
    }
    return [...map.values()].sort((a, b) => a.label.localeCompare(b.label, 'sr'))
  }, [parcels])

  return (
    <div className="w-full min-w-0 space-y-6 print:space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-4 print:hidden">
        <div>
          <p className="kicker">{tr("Izveštaji")}</p>
          <h1 className="mt-1 text-xl font-semibold tracking-tight sm:text-2xl">
            {tr('Zbirni izveštaj mreže')}
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            {tr('Pregled kao godišnji izveštaj parcele — samo dostupni podaci mreže {{name}}.', {
              name: organization?.name ?? '',
            })}
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          onClick={printReport}
          disabled={!report}
        >
          <Printer className="h-4 w-4" />
          {tr('Štampaj / PDF')}
        </Button>
      </div>

      <section className="space-y-3 rounded-2xl border border-border p-4 print:hidden">
        <div>
          <h2 className="text-sm font-semibold">Izvoz anomalija</h2>
          <p className="mt-1 text-xs text-muted-foreground">
            {tr('CSV postojećih alerta na dodeljenim parcelama. Prazna polja ostaju prazna.')}
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <label className="space-y-1 text-xs text-muted-foreground">
            Od
            <Input type="date" value={csvFrom} onChange={(e) => setCsvFrom(e.target.value)} />
          </label>
          <label className="space-y-1 text-xs text-muted-foreground">
            Do
            <Input type="date" value={csvTo} onChange={(e) => setCsvTo(e.target.value)} />
          </label>
          <label className="min-w-[10rem] flex-1 space-y-1 text-xs text-muted-foreground">
            {tr("Dobavljač")}
            <Select
              value={csvFarm}
              onChange={(e) => {
                setCsvFarm(e.target.value)
                setCsvParcel('')
              }}
            >
              <option value="">Svi</option>
              {supplierGroups.map((group) => (
                <option key={group.parcels[0]?.farm_id} value={group.parcels[0]?.farm_id}>
                  {group.label}
                </option>
              ))}
            </Select>
          </label>
          <label className="min-w-[10rem] flex-1 space-y-1 text-xs text-muted-foreground">
            {tr("Parcela")}
            <Select value={csvParcel} onChange={(e) => setCsvParcel(e.target.value)}>
              <option value="">Sve</option>
              {parcels
                .filter((parcel) => !csvFarm || parcel.farm_id === csvFarm)
                .map((parcel) => (
                  <option key={parcel.parcel_id} value={parcel.parcel_id}>
                    {parcel.parcel_name}
                  </option>
                ))}
            </Select>
          </label>
          <label className="space-y-1 text-xs text-muted-foreground">
            Ozbiljnost
            <Select value={csvSeverity} onChange={(e) => setCsvSeverity(e.target.value)}>
              <option value="">Sve</option>
              <option value="INFO">Info</option>
              <option value="WARNING">Upozorenje</option>
              <option value="CRITICAL">{tr("Kritično")}</option>
            </Select>
          </label>
          <label className="space-y-1 text-xs text-muted-foreground">
            Status
            <Select value={csvStatus} onChange={(e) => setCsvStatus(e.target.value)}>
              <option value="">Svi</option>
              <option value="open">Otvoren</option>
              <option value="acknowledged">Pregledan</option>
              <option value="resolved">{tr("Rešen")}</option>
            </Select>
          </label>
          <Button
            type="button"
            variant="outline"
            disabled={csvBusy}
            onClick={() => {
              const params = new URLSearchParams()
              if (csvFrom) params.set('date_from', csvFrom)
              if (csvTo) params.set('date_to', csvTo)
              if (csvFarm) params.set('farm_id', csvFarm)
              if (csvParcel) params.set('parcel_id', csvParcel)
              if (csvSeverity) params.set('severity', csvSeverity)
              if (csvStatus) params.set('alert_status', csvStatus)
              setCsvBusy(true)
              setCsvError(null)
              void downloadEnterpriseAlertCsv(organizationId, params)
                .catch((error: Error) => setCsvError(error.message))
                .finally(() => setCsvBusy(false))
            }}
          >
            Preuzmi CSV
          </Button>
        </div>
        {csvError ? <p className="text-sm text-danger">{csvError}</p> : null}
      </section>

      <section className="space-y-4 rounded-2xl border border-border p-4 print:hidden">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold">{tr('Obuhvat izveštaja')}</h2>
            <p className="mt-1 text-xs text-muted-foreground">
              {tr('Podrazumevano su sve parcele uključene. Izmena odmah osvežava pregled ispod.')}
            </p>
          </div>
          <div className="flex flex-wrap items-end gap-2">
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">{tr('Godina')}</label>
              <Input
                className="w-28"
                type="number"
                value={year}
                onChange={(e) => setYear(e.target.value)}
              />
            </div>
            <Button type="button" variant="outline" onClick={() => toggleAll(true)}>
              Sve
            </Button>
            <Button type="button" variant="outline" onClick={() => toggleAll(false)}>
              Nijedna
            </Button>
          </div>
        </div>

        <div className="grid max-h-56 gap-3 overflow-y-auto sm:grid-cols-2">
          {supplierGroups.map((group) => {
            const ids = group.parcels.map((p) => p.parcel_id)
            const selectedCount = ids.filter((id) => selected[id]).length
            const allOn = selectedCount === ids.length && ids.length > 0
            const someOn = selectedCount > 0 && !allOn
            return (
              <div key={group.label} className="rounded-xl border border-border/80 p-3">
                <label className="flex items-center gap-2 text-sm font-semibold">
                  <input
                    type="checkbox"
                    checked={allOn}
                    ref={(el) => {
                      if (el) el.indeterminate = someOn
                    }}
                    onChange={(e) => {
                      setSelected((prev) => {
                        const next = { ...prev }
                        for (const id of ids) next[id] = e.target.checked
                        return next
                      })
                    }}
                  />
                  {group.label}
                  <span className="font-normal text-muted-foreground">
                    ({selectedCount}/{ids.length})
                  </span>
                </label>
                <ul className="mt-2 space-y-1.5 pl-6">
                  {group.parcels.map((parcel) => (
                    <li key={parcel.parcel_id}>
                      <label className="flex cursor-pointer items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={Boolean(selected[parcel.parcel_id])}
                          onChange={(e) =>
                            setSelected((prev) => ({
                              ...prev,
                              [parcel.parcel_id]: e.target.checked,
                            }))
                          }
                        />
                        {parcel.parcel_name}
                      </label>
                    </li>
                  ))}
                </ul>
              </div>
            )
          })}
        </div>
      </section>

      {selectedIds.length === 0 ? (
        <p className="rounded-xl border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground print:hidden">
          {tr('Izaberite bar jednu parcelu da vidite pregled izveštaja.')}
        </p>
      ) : reportQuery.isLoading || reportQuery.isFetching ? (
        <p className="text-sm text-muted-foreground print:hidden">{tr('Priprema izveštaja…')}</p>
      ) : reportQuery.isError ? (
        <p className="text-sm text-danger print:hidden">
          {tr('Izveštaj nije učitan. Osvežite stranicu ili promenite obuhvat.')}
        </p>
      ) : report ? (
        <AggregateReportDocument report={report} />
      ) : null}
    </div>
  )
}

function AggregateReportDocument({ report }: { report: EnterpriseAggregateReport }) {
  const generated = formatReportDate(report.generated_on)

  return (
    <article className="report-sheet min-w-0 space-y-6 rounded-xl border border-border bg-card px-4 py-5 sm:space-y-8 sm:px-8 sm:py-8 print:space-y-6 print:rounded-none print:border-0 print:bg-white print:px-0 print:py-0">
      <header className="print-avoid border-b border-border pb-5 sm:pb-6">
        <div className="flex items-center justify-between gap-4">
          <div className="flex min-w-0 items-center gap-3">
            <BrandLogo variant="mark" className="h-9 w-9 shrink-0 object-contain sm:h-10 sm:w-10" />
            <div className="min-w-0">
              <p className="wordmark text-base leading-none sm:text-lg">
                <span className="wordmark-agro">Agro</span>
                <span className="wordmark-twin">Twin</span>
              </p>
              <p className="mt-1 text-[10px] font-semibold tracking-[0.16em] text-muted-foreground uppercase">
                {tr('Zbirni izveštaj mreže')}
              </p>
            </div>
          </div>
          <div className="shrink-0 text-right">
            <p className="text-3xl font-semibold tabular-nums tracking-tight text-primary sm:text-4xl">
              {report.year}
            </p>
            <p className="mt-0.5 text-[11px] text-muted-foreground">sezona</p>
          </div>
        </div>
        <h2 className="mt-5 text-2xl font-semibold tracking-tight sm:mt-6 sm:text-3xl">
          {report.organization_name}
        </h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Generisano kroz AgroTwin platformu · {generated}
        </p>
      </header>

      <section className="print-avoid">
        <SectionTitle>Pregled sezone</SectionTitle>
        <div className="mt-5 grid grid-cols-2 gap-3 lg:grid-cols-3">
          <KpiCard label={tr('Parcele')} value={formatNumber(report.parcel_count)} />
          {report.total_area_ha != null ? (
            <KpiCard label={tr("Površina")} value={`${formatNumber(report.total_area_ha)} ha`} />
          ) : null}
          {report.total_trees != null ? (
            <KpiCard label={tr("Stabla")} value={formatNumber(report.total_trees)} />
          ) : null}
          {report.expected_yield_kg != null ? (
            <KpiCard
              label={tr("Očekivani prinos")}
              value={`${formatNumber(report.expected_yield_kg)} kg`}
            />
          ) : (
            <KpiCard label={tr("Očekivani prinos")} value={tr('Nije dostupno')} muted />
          )}
          {report.actual_yield_kg != null ? (
            <KpiCard
              label={tr('Ostvareni prinos')}
              value={`${formatNumber(report.actual_yield_kg)} kg`}
            />
          ) : (
            <KpiCard label={tr('Ostvareni prinos')} value={tr('Nije dostupno')} muted />
          )}
          {report.harvest_coverage_percent != null ? (
            <KpiCard
              label={tr("Pokriće berbe")}
              value={`${formatNumber(report.harvest_coverage_percent)}%`}
            />
          ) : (
            <KpiCard label={tr("Pokriće berbe")} value={tr('Nije dostupno')} muted />
          )}
          <KpiCard label="Otkupi" value={formatNumber(report.purchase_count ?? 0)} />
          {report.purchased_quantity_kg != null ? (
            <KpiCard
              label="Otkupljeno"
              value={`${formatNumber(report.purchased_quantity_kg)} kg`}
            />
          ) : (
            <KpiCard label="Otkupljeno" value={tr('Nije dostupno')} muted />
          )}
          <KpiCard
            label="Iznos otkupa"
            value={
              Object.keys(report.purchase_totals_by_currency ?? {}).length > 0
                ? Object.entries(report.purchase_totals_by_currency)
                    .map(([cur, amt]) => `${formatNumber(amt)} ${cur}`)
                    .join(' · ')
                : tr('Nije dostupno')
            }
            muted={Object.keys(report.purchase_totals_by_currency ?? {}).length === 0}
          />
        </div>
      </section>

      <section className="print-avoid">
        <SectionTitle>{tr('Parcele u izveštaju')}</SectionTitle>
        <div className="print-scroll-x mt-4 overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-border text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="py-2.5 pr-3">{tr("Parcela")}</th>
                <th className="py-2.5 pr-3">{tr("Proizvođač")}</th>
                <th className="py-2.5 pr-3">Sorte</th>
                <th className="py-2.5 pr-3">{tr("Površina")}</th>
                <th className="py-2.5 pr-3">{tr("Stabla")}</th>
                <th className="py-2.5 pr-3">{tr("Očekivano")}</th>
                <th className="py-2.5">{tr("Ostvareno")}</th>
              </tr>
            </thead>
            <tbody>
              {report.parcels.map((parcel) => (
                <tr key={parcel.parcel_id} className="border-b border-border/70">
                  <td className="py-2.5 pr-3 font-medium">{parcel.parcel_name}</td>
                  <td className="py-2.5 pr-3">{parcel.producer_display_name ?? '—'}</td>
                  <td className="py-2.5 pr-3">
                    {parcel.variety_names.length > 0 ? parcel.variety_names.join(', ') : '—'}
                  </td>
                  <td className="py-2.5 pr-3 tabular-nums">
                    {parcel.area_hectares != null
                      ? `${formatNumber(parcel.area_hectares)} ha`
                      : '—'}
                  </td>
                  <td className="py-2.5 pr-3 tabular-nums">{formatNumber(parcel.tree_count)}</td>
                  <td className="py-2.5 pr-3 tabular-nums text-primary">
                    {parcel.expected_yield_kg != null
                      ? `${formatNumber(parcel.expected_yield_kg)} kg`
                      : '—'}
                  </td>
                  <td className="py-2.5 tabular-nums">
                    {parcel.actual_yield_kg != null
                      ? `${formatNumber(parcel.actual_yield_kg)} kg`
                      : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="print-avoid">
        <SectionTitle>{tr('Realizovani otkupi')}</SectionTitle>
        <p className="mt-2 text-sm text-muted-foreground">
          {tr(
            'Otkupi Enterprise-a od dobavljača čije su parcele u obuhvatu izveštaja · sezona {{year}}.',
            { year: report.year },
          )}
        </p>

        {(report.purchases_by_supplier ?? []).length > 0 ? (
          <div className="print-scroll-x mt-4 overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="border-b border-border text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="py-2.5 pr-3">{tr("Dobavljač")}</th>
                  <th className="py-2.5 pr-3">Otkupi</th>
                  <th className="py-2.5 pr-3">{tr("Količina")}</th>
                  <th className="py-2.5">Iznos</th>
                </tr>
              </thead>
              <tbody>
                {report.purchases_by_supplier.map((row) => (
                  <tr key={row.farm_id} className="border-b border-border/70">
                    <td className="py-2.5 pr-3 font-medium">
                      {row.producer_display_name || row.farm_name || '—'}
                    </td>
                    <td className="py-2.5 pr-3 tabular-nums">{formatNumber(row.purchase_count)}</td>
                    <td className="py-2.5 pr-3 tabular-nums">
                      {row.quantity_kg != null ? `${formatNumber(row.quantity_kg)} kg` : '—'}
                    </td>
                    <td className="py-2.5 tabular-nums">
                      {Object.keys(row.amount_by_currency ?? {}).length > 0
                        ? Object.entries(row.amount_by_currency)
                            .map(([cur, amt]) => `${formatNumber(amt)} ${cur}`)
                            .join(' · ')
                        : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}

        {(report.purchases ?? []).length > 0 ? (
          <div className="print-scroll-x mt-5 overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="border-b border-border text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="py-2.5 pr-3">Datum</th>
                  <th className="py-2.5 pr-3">{tr("Dobavljač")}</th>
                  <th className="py-2.5 pr-3">Osnova</th>
                  <th className="py-2.5 pr-3">{tr("Količina")}</th>
                  <th className="py-2.5 pr-3">Cena / kg</th>
                  <th className="py-2.5">Iznos</th>
                </tr>
              </thead>
              <tbody>
                {report.purchases.map((row) => (
                  <tr key={row.purchase_id} className="border-b border-border/70">
                    <td className="py-2.5 pr-3">{row.purchased_on}</td>
                    <td className="py-2.5 pr-3 font-medium">
                      {row.producer_display_name || row.farm_name || '—'}
                    </td>
                    <td className="py-2.5 pr-3 capitalize">{row.quantity_basis}</td>
                    <td className="py-2.5 pr-3 tabular-nums">
                      {formatNumber(row.quantity_kg)} kg
                    </td>
                    <td className="py-2.5 pr-3 tabular-nums">
                      {formatNumber(row.unit_price_per_kg)} {row.currency}
                    </td>
                    <td className="py-2.5 tabular-nums font-medium text-primary">
                      {formatNumber(row.total_amount)} {row.currency}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="mt-4 text-sm text-muted-foreground">
            Nema realizovanih otkupa za odabrani obuhvat u ovoj sezoni.
          </p>
        )}
      </section>

      {report.notes.length > 0 ? (
        <section className="print-avoid">
          <SectionTitle>Napomene</SectionTitle>
          <ul className="mt-3 space-y-1.5 text-sm text-muted-foreground">
            {report.notes.map((note) => (
              <li key={note}>• {note}</li>
            ))}
          </ul>
        </section>
      ) : null}

      <footer className="print-avoid border-t border-border pt-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <BrandLogo variant="mark" className="h-5 w-5 object-contain opacity-80" />
            <p className="text-[11px] text-muted-foreground">
              {tr('AgroTwin · {{org}} · {{generated}} · sažetak evidencije mreže, bez predikcija', {
                org: report.organization_name,
                generated,
              })}
            </p>
          </div>
        </div>
      </footer>
    </article>
  )
}

function formatReportDate(value: string) {
  const date = new Date(`${value}T12:00:00`)
  if (Number.isNaN(date.getTime())) return formatDate(value)
  return date.toLocaleDateString(LOCALE, {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
}

function SectionTitle({ children }: { children: ReactNode }) {
  return (
    <h2 className="flex items-center gap-2.5 text-xs font-bold tracking-[0.18em] text-accent uppercase">
      <span
        className="inline-block h-3.5 w-1 shrink-0 rounded-full bg-accent/80 print:bg-[#026a74]"
        aria-hidden
      />
      {children}
    </h2>
  )
}

function KpiCard({
  label,
  value,
  muted,
}: {
  label: string
  value: string
  muted?: boolean
}) {
  return (
    <article className="print-avoid rounded-xl border border-border bg-background px-3 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.65)] sm:px-4 sm:py-4 print:border-[#c5d5ca] print:bg-[#f7fbf8] print:shadow-none">
      <p className="truncate text-[10px] font-semibold uppercase tracking-wide text-muted-foreground sm:text-[11px]">
        {label}
      </p>
      <p
        className={
          muted
            ? 'mt-1.5 text-base font-semibold tracking-tight text-muted-foreground sm:mt-2 sm:text-lg'
            : 'mt-1.5 text-xl font-semibold tracking-tight tabular-nums text-primary sm:mt-2 sm:text-2xl'
        }
      >
        {value}
      </p>
    </article>
  )
}
