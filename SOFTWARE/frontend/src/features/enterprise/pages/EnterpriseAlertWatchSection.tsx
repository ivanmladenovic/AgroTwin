import { useMemo, useState, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'

import {
  getEnterpriseAlertWatch,
  reviewEnterpriseAlert,
  type EnterpriseAlertWatchParams,
} from '@/features/enterprise/api'
import { useEnterprise } from '@/features/enterprise/EnterpriseContext'
import { anomalyKindLabel, zoneKeyLabel } from '@/features/orchard/monitoring/satelliteLabels'
import { cn } from '@/shared/lib/utils'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Select } from '@/shared/ui/select'
import type { EnterpriseAlertWatchItem, EnterpriseMonitoringFiltersMeta } from '@/shared/api/types'

import { tr } from '@/shared/i18n/i18n'
const PAGE_SIZE = 50

const ALERT_STATUSES = [
  { value: 'open', labelKey: 'Otvoren' },
  { value: 'acknowledged', labelKey: 'Potvrđen' },
  { value: 'resolved', labelKey: 'Rešen' },
]

const SEVERITIES = [
  { value: 'INFO', labelKey: 'Info' },
  { value: 'WARNING', labelKey: 'Upozorenje' },
  { value: 'CRITICAL', labelKey: 'Kritično' },
]

export function EnterpriseAlertWatchSection({
  suppliers,
  parcels,
}: {
  suppliers: EnterpriseMonitoringFiltersMeta['suppliers']
  parcels: EnterpriseMonitoringFiltersMeta['parcels']
}) {
  useTranslation()
  const { organizationId, canWritePlans } = useEnterprise()
  const [searchParams, setSearchParams] = useSearchParams()
  const queryClient = useQueryClient()
  const filters = useMemo(() => parseAlertFilters(searchParams), [searchParams])
  const [notes, setNotes] = useState<Record<string, string>>({})
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [showMoreFilters, setShowMoreFilters] = useState(hasExtraAlertFilters(filters))

  const watchQuery = useQuery({
    queryKey: ['enterprise-alert-watch', organizationId, filters],
    queryFn: () => getEnterpriseAlertWatch(organizationId, filters),
  })
  const review = useMutation({
    mutationFn: ({ alertId, note }: { alertId: string; note?: string }) =>
      reviewEnterpriseAlert(organizationId, alertId, note),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['enterprise-alert-watch', organizationId] })
    },
  })

  const data = watchQuery.data
  const farmId = filters.farm_id
  const parcelOptions = farmId ? parcels.filter((item) => item.farm_id === farmId) : parcels
  const offset = filters.offset ?? 0
  const total = data?.alert_count ?? 0
  const shownFrom = total === 0 ? 0 : offset + 1
  const shownTo = Math.min(offset + (data?.items.length ?? 0), total)

  function setField(key: string, value: string) {
    const next = new URLSearchParams(searchParams)
    if (!value) next.delete(key)
    else next.set(key, value)
    if (key !== 'alert_offset') next.delete('alert_offset')
    setSearchParams(next, { replace: true })
  }

  function clearAlertFilters() {
    const next = new URLSearchParams(searchParams)
    for (const key of [...next.keys()]) {
      if (key.startsWith('alert_')) next.delete(key)
    }
    setSearchParams(next, { replace: true })
    setShowMoreFilters(false)
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        {tr('AI sažetak je tumačenje zapisa, ne potvrđena dijagnoza. Pregled kompanije ne menja status kod')}
        {tr('proizvođača.')}
      </p>

      <div className="flex flex-wrap items-end gap-3">
        <Field label={tr("Proizvođač")} className="min-w-[10rem] flex-1">
          <Select
            value={filters.farm_id ?? ''}
            onChange={(e) => {
              const next = new URLSearchParams(searchParams)
              if (!e.target.value) next.delete('alert_farm_id')
              else next.set('alert_farm_id', e.target.value)
              next.delete('alert_parcel_id')
              next.delete('alert_offset')
              setSearchParams(next, { replace: true })
            }}
          >
            <option value="">{tr('Svi proizvođači')}</option>
            {suppliers.map((item) => (
              <option key={item.farm_id} value={item.farm_id}>
                {item.label}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={tr("Parcela")} className="min-w-[10rem] flex-1">
          <Select
            value={filters.parcel_id ?? ''}
            onChange={(e) => setField('alert_parcel_id', e.target.value)}
          >
            <option value="">{tr('Sve parcele')}</option>
            {parcelOptions.map((item) => (
              <option key={item.parcel_id} value={item.parcel_id}>
                {item.label}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Status" className="min-w-[8rem]">
          <Select
            value={filters.alert_status ?? ''}
            onChange={(e) => setField('alert_status', e.target.value)}
          >
            <option value="">Svi</option>
            {ALERT_STATUSES.map((item) => (
              <option key={item.value} value={item.value}>
                {tr(item.labelKey)}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={tr("Pregled")} className="min-w-[9rem]">
          <Select
            value={filters.review_status ?? ''}
            onChange={(e) => setField('alert_review', e.target.value)}
          >
            <option value="">Svi</option>
            <option value="unreviewed">{tr('Nije pregledano')}</option>
            <option value="reviewed">Pregledano</option>
          </Select>
        </Field>
        <div className="flex flex-wrap gap-2 pb-0.5">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => setShowMoreFilters((value) => !value)}
          >
            {showMoreFilters ? tr('Manje filtera') : tr('Više filtera')}
          </Button>
          {hasAnyAlertFilter(filters) ? (
            <Button type="button" variant="outline" size="sm" onClick={clearAlertFilters}>
              {tr('Obriši')}
            </Button>
          ) : null}
        </div>
      </div>

      {showMoreFilters ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="Datum od">
            <Input
              type="date"
              value={filters.date_from ?? ''}
              onChange={(e) => setField('alert_date_from', e.target.value)}
            />
          </Field>
          <Field label="Datum do">
            <Input
              type="date"
              value={filters.date_to ?? ''}
              onChange={(e) => setField('alert_date_to', e.target.value)}
            />
          </Field>
          <Field label="Indeks">
            <Select
              value={filters.index ?? ''}
              onChange={(e) => setField('alert_index', e.target.value)}
            >
              <option value="">{tr('Svi indeksi')}</option>
              <option value="ndvi">NDVI</option>
              <option value="ndre">NDRE</option>
              <option value="ndwi">NDWI</option>
            </Select>
          </Field>
          <Field label="Ozbiljnost">
            <Select
              value={filters.severity ?? ''}
              onChange={(e) => setField('alert_severity', e.target.value)}
            >
              <option value="">{tr('Sve ozbiljnosti')}</option>
              {SEVERITIES.map((item) => (
                <option key={item.value} value={item.value}>
                  {tr(item.labelKey)}
                </option>
              ))}
            </Select>
          </Field>
        </div>
      ) : null}

      <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
        <span>
          <span className="text-muted-foreground">Otvoreni: </span>
          <span className="font-semibold tabular-nums">{data?.open_alerts ?? '—'}</span>
        </span>
        <span>
          <span className="text-muted-foreground">{tr('U filteru:')} </span>
          <span className="font-semibold tabular-nums">{data?.alert_count ?? '—'}</span>
        </span>
        <span>
          <span className="text-muted-foreground">Anomalije: </span>
          <span className="font-semibold tabular-nums">{data?.satellite_anomaly_count ?? '—'}</span>
        </span>
      </div>

      {watchQuery.isLoading ? <p className="text-sm text-muted-foreground">{tr('Učitavanje alerta…')}</p> : null}
      {watchQuery.isError ? <p className="text-sm text-danger">{tr('Alerti nisu učitani.')}</p> : null}
      {review.isError ? (
        <p className="text-sm text-danger">{tr('Pregled nije sačuvan. Proverite ulogu naloga.')}</p>
      ) : null}

      {data && data.items.length === 0 ? (
        <p className="rounded-xl border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
          Nema alerta za izabrani filter.
        </p>
      ) : null}

      <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border">
        {(data?.items ?? []).map((item) => {
          const open = expandedId === item.alert_id
          return (
            <li key={item.alert_id} className="bg-background">
              <div className="flex flex-wrap items-start gap-3 px-3 py-3 sm:px-4">
                <button
                  type="button"
                  className="mt-0.5 text-muted-foreground"
                  aria-expanded={open}
                  aria-label={open ? 'Skupi detalje' : tr('Proširi detalje')}
                  onClick={() => setExpandedId(open ? null : item.alert_id)}
                >
                  {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                </button>
                <div className="min-w-0 flex-1 space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <SeverityBadge value={item.severity} />
                    <span className="text-[11px] uppercase tracking-wide text-muted-foreground">
                      {statusLabel(item.status)}
                    </span>
                    {!item.company_review ? (
                      <span className="rounded bg-[#f3e2b0] px-1.5 py-0.5 text-[11px] font-semibold text-[#3d2e04]">
                        Nije pregledano
                      </span>
                    ) : (
                      <span className="rounded bg-[#d7ead8] px-1.5 py-0.5 text-[11px] font-semibold text-[#1d4a22]">
                        Pregledano
                      </span>
                    )}
                  </div>
                  <button
                    type="button"
                    className="text-left text-sm font-semibold hover:underline"
                    onClick={() => setExpandedId(open ? null : item.alert_id)}
                  >
                    {item.title}
                  </button>
                  <p className="text-xs text-muted-foreground">
                    {item.producer_name || tr('Nema podataka')} · {item.parcel_name}
                    {item.observation_date ? ` · snimak ${item.observation_date}` : ''}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button variant="outline" size="sm" asChild>
                    <Link to={item.intelligence_path}>Intelligence</Link>
                  </Button>
                  {canWritePlans && !item.company_review ? (
                    <Button
                      type="button"
                      size="sm"
                      disabled={review.isPending}
                      onClick={() => review.mutate({ alertId: item.alert_id })}
                    >
                      {tr('Označi pregledano')}
                    </Button>
                  ) : null}
                </div>
              </div>

              {open ? (
                <div className="space-y-3 border-t border-border bg-muted/20 px-3 py-3 sm:px-4 sm:pl-11">
                  <dl className="grid gap-2 text-sm sm:grid-cols-2">
                    <Fact label="Indeks" value={item.affected_indices.map((i) => i.toUpperCase()).join(', ')} />
                    <Fact
                      label="Tip anomalije"
                      value={item.anomaly_kinds.map((kind) => anomalyKindLabel(kind)).join(', ')}
                    />
                    {item.tree_public_ids?.length ? (
                      <Fact label={tr("Stabla")} value={item.tree_public_ids.slice(0, 8).join(', ')} />
                    ) : item.zone_keys.length ? (
                      <Fact
                        label={tr('Deo parcele')}
                        value={item.zone_keys.map((key) => zoneKeyLabel(key) ?? key).join(', ')}
                      />
                    ) : null}
                    <Fact label="Poslednja analiza" value={formatWhen(item.last_analysis_at)} />
                    {showLatestObservation(item) ? (
                      <Fact label="Poslednja opservacija" value={item.latest_observation_date} />
                    ) : null}
                    <Fact
                      label={tr("Pregled kompanije")}
                      value={
                        item.company_review
                          ? `Pregledano ${formatWhen(item.company_review.reviewed_at)}${
                              item.company_review.reviewed_by_name
                                ? ` · ${item.company_review.reviewed_by_name}`
                                : ''
                            }`
                          : tr('Nije pregledano')
                      }
                    />
                  </dl>

                  {item.summary ? (
                    <div className="text-sm">
                      <p className="whitespace-pre-wrap">{item.summary}</p>
                      {item.recommended_actions.length ? (
                        <ul className="mt-2 list-disc pl-5 text-muted-foreground">
                          {item.recommended_actions.map((action) => (
                            <li key={action}>{action}</li>
                          ))}
                        </ul>
                      ) : null}
                      {item.disclaimer ? (
                        <p className="mt-2 text-xs text-muted-foreground">{item.disclaimer}</p>
                      ) : null}
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">{tr('Nema AI sažetka.')}</p>
                  )}

                  {item.company_review?.note ? (
                    <p className="text-sm text-muted-foreground">Napomena: {item.company_review.note}</p>
                  ) : null}

                  {canWritePlans ? (
                    <div className="flex flex-wrap items-end gap-2">
                      <Input
                        value={notes[item.alert_id] ?? ''}
                        placeholder={tr('Interna napomena (opciono)')}
                        onChange={(e) =>
                          setNotes((current) => ({ ...current, [item.alert_id]: e.target.value }))
                        }
                      />
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        disabled={review.isPending}
                        onClick={() =>
                          review.mutate({ alertId: item.alert_id, note: notes[item.alert_id] })
                        }
                      >
                        {item.company_review ? tr('Ažuriraj pregled') : tr('Označi kao pregledano')}
                      </Button>
                    </div>
                  ) : null}
                </div>
              ) : null}
            </li>
          )
        })}
      </ul>

      {total > PAGE_SIZE ? (
        <div className="flex items-center justify-between gap-3 text-sm">
          <p className="text-muted-foreground">
            {shownFrom}–{shownTo} od {total}
          </p>
          <div className="flex gap-2">
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={offset <= 0}
              onClick={() => setField('alert_offset', String(Math.max(0, offset - PAGE_SIZE)))}
            >
              Prethodna
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={offset + PAGE_SIZE >= total}
              onClick={() => setField('alert_offset', String(offset + PAGE_SIZE))}
            >
              {tr('Sledeća')}
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  )
}

function parseAlertFilters(params: URLSearchParams): EnterpriseAlertWatchParams {
  const offset = Number(params.get('alert_offset') || '0')
  return {
    date_from: params.get('alert_date_from') || undefined,
    date_to: params.get('alert_date_to') || undefined,
    farm_id: params.get('alert_farm_id') || undefined,
    parcel_id: params.get('alert_parcel_id') || undefined,
    index: params.get('alert_index') || undefined,
    severity: params.get('alert_severity') || undefined,
    alert_status: params.get('alert_status') || undefined,
    review_status: params.get('alert_review') || undefined,
    limit: PAGE_SIZE,
    offset: Number.isFinite(offset) && offset > 0 ? offset : 0,
  }
}

function hasExtraAlertFilters(filters: EnterpriseAlertWatchParams) {
  return Boolean(filters.date_from || filters.date_to || filters.index || filters.severity)
}

function hasAnyAlertFilter(filters: EnterpriseAlertWatchParams) {
  return Boolean(
    filters.date_from ||
      filters.date_to ||
      filters.farm_id ||
      filters.parcel_id ||
      filters.index ||
      filters.severity ||
      filters.alert_status ||
      filters.review_status,
  )
}

function showLatestObservation(item: EnterpriseAlertWatchItem) {
  if (!item.latest_observation_date) return false
  if (!item.processed_at) return item.latest_observation_date !== item.observation_date
  return item.latest_observation_date !== item.processed_at.slice(0, 10)
}

function Fact({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd>{value && value.trim() ? value : tr('Nema podataka')}</dd>
    </div>
  )
}

function Field({
  label,
  children,
  className,
}: {
  label: string
  children: ReactNode
  className?: string
}) {
  return (
    <label className={cn('block space-y-1 text-xs font-medium text-muted-foreground', className)}>
      {label}
      {children}
    </label>
  )
}

function SeverityBadge({ value }: { value: string }) {
  return (
    <span
      className={cn(
        'rounded px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide',
        value === 'CRITICAL' && 'bg-danger/15 text-danger',
        value === 'WARNING' && 'bg-[#f3e2b0] text-[#3d2e04]',
        value === 'INFO' && 'bg-muted text-muted-foreground',
        !['CRITICAL', 'WARNING', 'INFO'].includes(value) && 'bg-muted text-muted-foreground',
      )}
    >
      {severityLabel(value)}
    </span>
  )
}

function severityLabel(value: string) {
  const key = SEVERITIES.find((item) => item.value === value)?.labelKey
  return key ? tr(key) : value
}

function statusLabel(value: string) {
  const key = ALERT_STATUSES.find((item) => item.value === value)?.labelKey
  return key ? tr(key) : value
}

function formatWhen(value: string | null) {
  if (!value) return null
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('sr-RS')
}
