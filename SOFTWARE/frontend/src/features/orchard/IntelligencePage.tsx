import { useEffect } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  acknowledgeIntelligenceAlert,
  getParcel,
  getParcelIntelligence,
  requestParcelIntelligence,
  resolveIntelligenceAlert,
} from '@/features/orchard/api'
import {
  humanizeZoneKeysInText,
  indexNameLabel,
  locationFromZone,
  treeIdsLabel,
} from '@/features/orchard/monitoring/satelliteLabels'
import type { ParcelAlert, ParcelAlertEvidence } from '@/shared/api/types'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'

import { tr } from '@/shared/i18n/i18n'
export function IntelligencePage() {
  const { parcelId = '' } = useParams()
  const [searchParams] = useSearchParams()
  const alertId = searchParams.get('alert')
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const intelQuery = useQuery({
    queryKey: ['parcel-intelligence', parcelId],
    queryFn: () => getParcelIntelligence(parcelId),
    enabled: Boolean(parcelId),
  })
  const readOnly = Boolean(intelQuery.data?.read_only)
  const canMutate = intelQuery.isSuccess && !readOnly
  const parcelQuery = useQuery({
    queryKey: ['parcel', parcelId],
    queryFn: () => getParcel(parcelId),
    enabled: Boolean(parcelId) && intelQuery.isSuccess && !readOnly,
  })
  useEffect(() => {
    if (!alertId || !intelQuery.data) return
    document.getElementById(`alert-${alertId}`)?.scrollIntoView({ block: 'center' })
  }, [alertId, intelQuery.data])
  const invalidate = () => void queryClient.invalidateQueries({ queryKey: ['parcel-intelligence', parcelId] })
  const analyze = useMutation({
    mutationFn: () => requestParcelIntelligence(parcelId),
    onSuccess: invalidate,
  })
  const acknowledge = useMutation({
    mutationFn: (alertId: string) => acknowledgeIntelligenceAlert(alertId),
    onSuccess: invalidate,
  })
  const resolve = useMutation({
    mutationFn: (alertId: string) => resolveIntelligenceAlert(alertId),
    onSuccess: invalidate,
  })

  const data = intelQuery.data

  return (
    <div className="mx-auto w-full max-w-5xl space-y-6 pb-16">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          {canMutate ? (
            <Link to={`/orchard/${parcelId}`} className="text-sm font-medium text-primary hover:underline">
              {tr('← Nazad na parcelu')}
            </Link>
          ) : (
            <button
              type="button"
              className="text-sm font-medium text-primary hover:underline"
              onClick={() => navigate(-1)}
            >
              {tr('← Nazad')}
            </button>
          )}
          <h1 className="mt-2 text-xl font-semibold sm:text-2xl">AgroTwin Intelligence</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {tr('{{name}} · kontinuirani monitoring (bez potvrđenih dijagnoza)', {
              name: parcelQuery.data?.name || data?.parcel_name || tr('Parcela'),
            })}
          </p>
        </div>
        {canMutate ? (
          <Button size="sm" disabled={analyze.isPending} onClick={() => analyze.mutate()}>
            {analyze.isPending ? tr('Analiza…') : tr('Pokreni analizu')}
          </Button>
        ) : null}
      </div>

      {intelQuery.isLoading ? <p className="text-sm text-muted-foreground">{tr('Učitavanje…')}</p> : null}
      {intelQuery.isError ? <p className="text-sm text-danger">{tr('Podaci nisu učitani.')}</p> : null}

      {data ? (
        <>
          <Card>
            <CardHeader>
              <CardTitle>{tr('Status analize')}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-1 text-sm text-muted-foreground">
              <p>
                {tr('Poslednja analiza:')}{' '}
                {data.last_analysis?.started_at
                  ? new Date(data.last_analysis.started_at).toLocaleString('sr-RS')
                  : '—'}
              </p>
              <p>
                {tr('AI pozvan:')}{' '}
                {data.last_analysis
                  ? data.last_analysis.ai_called
                    ? tr('da')
                    : tr('ne ({{reason}})', { reason: data.last_analysis.skip_reason || '—' })
                  : '—'}
              </p>
              <p>
                {tr('Sledeća planirana:')}{' '}
                {data.next_scheduled_at
                  ? new Date(data.next_scheduled_at).toLocaleString('sr-RS')
                  : '—'}
              </p>
            </CardContent>
          </Card>

          <AlertSection
            title={tr('Aktivni alerti')}
            empty={tr("Nema aktivnih alertova.")}
            parcelId={parcelId}
            alerts={data.active_alerts}
            highlightedId={alertId}
            readOnly={readOnly}
            onAcknowledge={readOnly ? undefined : (id) => acknowledge.mutate(id)}
            onResolve={readOnly ? undefined : (id) => resolve.mutate(id)}
          />

          <AlertSection
            title={tr("Rešeni alerti")}
            empty={tr("Nema rešenih alertova.")}
            parcelId={parcelId}
            alerts={data.resolved_alerts}
            highlightedId={alertId}
            readOnly={readOnly}
          />

          {data.disclaimer ? <p className="text-xs text-muted-foreground">{data.disclaimer}</p> : null}
        </>
      ) : null}
    </div>
  )
}

function AlertSection({
  title,
  empty,
  parcelId,
  alerts,
  highlightedId,
  readOnly,
  onAcknowledge,
  onResolve,
}: {
  title: string
  empty: string
  parcelId: string
  alerts: ParcelAlert[]
  highlightedId?: string | null
  readOnly?: boolean
  onAcknowledge?: (id: string) => void
  onResolve?: (id: string) => void
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {alerts.length === 0 ? <p className="text-sm text-muted-foreground">{empty}</p> : null}
        {alerts.map((alert) => (
          <div
            key={alert.id}
            id={`alert-${alert.id}`}
            className={
              highlightedId === alert.id
                ? 'space-y-3 rounded-lg border border-primary p-3 ring-2 ring-primary/40'
                : 'space-y-3 rounded-lg border border-border p-3'
            }
          >
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  {severityLabel(alert.severity)} · {statusLabel(alert.status)}
                </p>
                <p className="text-base font-medium">
                  {humanizeZoneKeysInText(alert.title, alert.evidence?.tree_public_ids)}
                </p>
                <p className="mt-1 text-sm text-muted-foreground">
                  {humanizeZoneKeysInText(alert.summary, alert.evidence?.tree_public_ids)}
                </p>
              </div>
              {(onAcknowledge || onResolve) && alert.status !== 'resolved' ? (
                <div className="flex gap-2">
                  {onAcknowledge && alert.status === 'open' ? (
                    <Button variant="outline" size="sm" onClick={() => onAcknowledge(alert.id)}>
                      {tr('Potvrdi')}
                    </Button>
                  ) : null}
                  {onResolve ? (
                    <Button variant="outline" size="sm" onClick={() => onResolve(alert.id)}>
                      {tr('Reši')}
                    </Button>
                  ) : null}
                </div>
              ) : null}
            </div>

            <EvidenceBlock parcelId={parcelId} evidence={alert.evidence} readOnly={readOnly} />
            <FactBlock
              label={tr("Šta se vidi")}
              items={alert.observed_facts}
              treeIds={alert.evidence?.tree_public_ids}
            />
            <FactBlock
              label={tr("Mogući razlozi")}
              items={alert.possible_causes}
              treeIds={alert.evidence?.tree_public_ids}
            />
            <FactBlock
              label={tr("Šta uraditi")}
              items={alert.recommended_actions}
              treeIds={alert.evidence?.tree_public_ids}
            />
            <FactBlock
              label={tr('Napomene o snimku')}
              items={alert.evidence?.data_quality_notes ?? []}
              treeIds={alert.evidence?.tree_public_ids}
            />
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

function EvidenceBlock({
  parcelId,
  evidence,
  readOnly,
}: {
  parcelId: string
  evidence?: ParcelAlertEvidence
  readOnly?: boolean
}) {
  if (!evidence) return null
  const zones = evidence.zone_keys ?? []
  const treeIds = evidence.tree_public_ids ?? []
  const indices = evidence.affected_indices ?? []
  const date = evidence.observation_date
  const whereLabel = treeIdsLabel(treeIds) ?? (zones.length ? zones.map((key) => locationFromZone(key)).filter(Boolean).join('; ') : null)
  if (!zones.length && !treeIds.length && !indices.length && !date) return null

  return (
    <div className="rounded-lg border border-border/70 bg-muted/20 px-3 py-2 text-sm">
      {date ? (
        <p>
          <span className="text-muted-foreground">{tr('Snimak:')} </span>
          {date}
        </p>
      ) : null}
      {indices.length ? (
        <p className="mt-1">
          <span className="text-muted-foreground">{tr('Šta merimo:')}</span>
          {indices.map((item) => indexNameLabel(item)).join(', ')}
        </p>
      ) : null}
      {whereLabel ? (
        <p className="mt-1">
          <span className="text-muted-foreground">
            {treeIds.length ? tr('Stabla: ') : tr('Gde na parceli: ')}
          </span>
          {whereLabel}
        </p>
      ) : null}
      {readOnly ? null : (
        <p className="mt-2 text-xs text-muted-foreground">
          {tr('Detaljnija mapa:')}{' '}
          <Link to={`/orchard/${parcelId}/satellite`} className="font-medium text-primary hover:underline">
            {tr('otvori monitoring')}
          </Link>
        </p>
      )}
    </div>
  )
}

function FactBlock({
  label,
  items,
  treeIds,
}: {
  label: string
  items: string[]
  treeIds?: string[]
}) {
  if (!items.length) return null
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>
      <ul className="mt-1 list-disc space-y-0.5 pl-5 text-sm">
        {items.map((item, index) => (
          <li key={`${index}-${item.slice(0, 24)}`}>
            {humanizeZoneKeysInText(item, treeIds)}
          </li>
        ))}
      </ul>
    </div>
  )
}

function severityLabel(value: string) {
  const map: Record<string, string> = {
    INFO: tr('Info'),
    WARNING: tr('Upozorenje'),
    CRITICAL: tr('Kritično'),
  }
  return map[value] ?? value
}

function statusLabel(value: string) {
  const map: Record<string, string> = {
    open: tr('otvoren'),
    acknowledged: tr('potvrđen'),
    resolved: tr('rešen'),
  }
  return map[value] ?? value
}

