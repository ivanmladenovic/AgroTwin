import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  getParcel,
  getParcelSatelliteMonitoring,
  getSatelliteObservation,
  refreshParcelSatellite,
  sampleSatelliteObservation,
  updateParcel,
} from '@/features/orchard/api'
import { ParcelBoundarySetupCard } from '@/features/orchard/ParcelBoundarySetupCard'
import {
  ParcelMonitoringMap,
  type IndexLayerId,
  type MapInspectPoint,
} from '@/features/orchard/monitoring/ParcelMonitoringMap'
import { aggregateAnomalyBriefing } from '@/features/orchard/monitoring/anomalyBriefing'
import { SatelliteHistoryPanel } from '@/features/orchard/monitoring/SatelliteHistoryPanel'
import { zoneTitle } from '@/features/orchard/monitoring/satelliteLabels'
import type { SatelliteObservation, SatelliteZone, VisualizationLayer } from '@/shared/api/types'
import { ApiError } from '@/shared/lib/api'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'

import { tr } from '@/shared/i18n/i18n'
function fmt(value: string | null | undefined, digits = 3) {
  if (value == null || value === '') return '—'
  const numeric = Number(value)
  if (Number.isNaN(numeric)) return '—'
  return numeric.toLocaleString('sr-RS', { maximumFractionDigits: digits })
}

function statusLabel(status: string | undefined, available: boolean | undefined) {
  if (!status) return tr('Nepoznato')
  if (status === 'ok' && available) return tr('Analiza završena')
  if (status === 'boundary_required') return tr('Nedostaje granica')
  if (status === 'no_observations') return tr('Nema opservacija')
  if (status === 'ok') return tr('U redu')
  if (status === 'pending') return tr('Na čekanju')
  if (status === 'processing') return tr('Obrada')
  if (status === 'completed') return tr('Završeno')
  if (status === 'failed') return tr('Neuspešno')
  if (status === 'skipped') return tr('Preskočeno')
  return status.replace(/[_-]+/g, ' ')
}

function pickIndexLayer(
  observation: SatelliteObservation | null | undefined,
  index: IndexLayerId,
): VisualizationLayer | null {
  if (!observation) return null
  const layers = observation.visualization_layers ?? []
  const match = layers.find((layer) => layer.index === index)
  if (match && Array.isArray(match.bbox) && match.bbox.length === 4) return match
  return null
}

function availableIndexLayers(observation: SatelliteObservation | null | undefined): IndexLayerId[] {
  if (!observation) return []
  const layers = observation.visualization_layers ?? []
  const ids: IndexLayerId[] = []
  for (const id of ['ndvi', 'ndre', 'ndwi'] as const) {
    const layer = layers.find((item) => item.index === id)
    if (layer && Array.isArray(layer.bbox) && layer.bbox.length === 4) ids.push(id)
  }
  return ids
}

export function SatelliteMonitoringPage() {
  const { parcelId = '' } = useParams()
  const queryClient = useQueryClient()
  const [activeIndex, setActiveIndex] = useState<IndexLayerId | null>('ndvi')
  const [selectedZoneKey, setSelectedZoneKey] = useState<string | null>(null)
  const [selectedObservationId, setSelectedObservationId] = useState<string | null>(null)
  const [compareId, setCompareId] = useState<string | null>(null)
  const [inspectPoint, setInspectPoint] = useState<MapInspectPoint | null>(null)
  const [boundaryMessage, setBoundaryMessage] = useState<string | null>(null)

  const parcelQuery = useQuery({
    queryKey: ['parcel', parcelId],
    queryFn: () => getParcel(parcelId),
    enabled: Boolean(parcelId),
  })
  const satQuery = useQuery({
    queryKey: ['parcel-satellite', parcelId],
    queryFn: () => getParcelSatelliteMonitoring(parcelId),
    enabled: Boolean(parcelId),
  })
  const refreshMutation = useMutation({
    mutationFn: () => refreshParcelSatellite(parcelId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['parcel-satellite', parcelId] })
    },
  })
  const boundaryMutation = useMutation({
    mutationFn: async (boundary: GeoJSON.Polygon) => {
      setBoundaryMessage(null)
      const updated = await updateParcel(parcelId, {
        boundary: boundary as unknown as Record<string, unknown>,
      })
      await queryClient.invalidateQueries({ queryKey: ['parcel', parcelId] })
      await queryClient.invalidateQueries({ queryKey: ['parcels'] })
      await queryClient.invalidateQueries({ queryKey: ['orchard-twin', parcelId] })
      try {
        await refreshParcelSatellite(parcelId)
        await queryClient.invalidateQueries({ queryKey: ['parcel-satellite', parcelId] })
        setBoundaryMessage(tr('Granica je sačuvana. Satelitski slojevi su ponovo isečeni na novu granicu.'))
      } catch {
        setBoundaryMessage(
          tr('Granica je sačuvana. Osvežavanje satelitskog sloja nije uspelo — kliknite „Osveži snimak“.'),
        )
      }
      autoRefreshAttempted.current = false
      return updated
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        setBoundaryMessage(error.message)
        return
      }
      setBoundaryMessage(error instanceof Error ? error.message : tr('Čuvanje granice nije uspelo.'))
    },
  })
  const autoRefreshAttempted = useRef(false)

  useEffect(() => {
    if (autoRefreshAttempted.current) return
    if (!satQuery.data || satQuery.data.available) return
    if (satQuery.data.status !== 'no_observations') return
    autoRefreshAttempted.current = true
    refreshMutation.mutate()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [satQuery.data?.status, satQuery.data?.available])

  const data = satQuery.data
  const latest = data?.latest ?? null

  useEffect(() => {
    if (latest?.id && !selectedObservationId) setSelectedObservationId(latest.id)
  }, [latest?.id, selectedObservationId])

  useEffect(() => {
    setSelectedZoneKey(null)
  }, [selectedObservationId])

  const observationQuery = useQuery({
    queryKey: ['satellite-observation', selectedObservationId],
    queryFn: () => getSatelliteObservation(selectedObservationId!),
    enabled: Boolean(selectedObservationId) && selectedObservationId !== latest?.id,
  })

  const activeObservation: SatelliteObservation | null = useMemo(() => {
    if (!selectedObservationId || selectedObservationId === latest?.id) return latest
    return observationQuery.data ?? latest
  }, [selectedObservationId, latest, observationQuery.data])

  const compareQuery = useQuery({
    queryKey: ['satellite-observation-compare', compareId],
    queryFn: () => getSatelliteObservation(compareId!),
    enabled: Boolean(compareId),
  })

  const zones: SatelliteZone[] = activeObservation?.zones ?? []
  const anomalyBriefing = useMemo(() => {
    if (!latest || selectedObservationId !== latest.id) return null
    return aggregateAnomalyBriefing(data?.anomalies ?? [], latest.zones ?? zones)
  }, [data?.anomalies, latest, selectedObservationId, zones])
  const capabilities = data?.capabilities
  const availableIndices = availableIndexLayers(activeObservation)
  const indexLayer = activeIndex ? pickIndexLayer(activeObservation, activeIndex) : null
  const compareAvailableIndices = availableIndexLayers(compareQuery.data)
  const compareIndexLayer =
    activeIndex && compareQuery.data ? pickIndexLayer(compareQuery.data, activeIndex) : null
  const selectedZone = zones.find((zone) => zone.zone_key === selectedZoneKey) ?? null
  const parcel = parcelQuery.data
  const compareMode = Boolean(compareId && compareQuery.data && activeObservation && parcel)
  useEffect(() => {
    if (availableIndices.length === 0) return
    // null = user turned the overlay off — do not force NDVI back on.
    if (activeIndex === null) return
    if (availableIndices.includes(activeIndex)) return
    setActiveIndex(availableIndices.includes('ndvi') ? 'ndvi' : availableIndices[0] ?? null)
  }, [availableIndices, activeIndex])

  async function handleMapInspect(lat: number, lng: number) {
    if (!activeObservation?.id || !activeIndex) {
      setInspectPoint({
        lat,
        lng,
        loading: false,
        sample: {
          observation_id: '',
          index: activeIndex ?? 'ndvi',
          acquisition_date: activeObservation?.acquisition_date ?? '',
          longitude: lng,
          latitude: lat,
          value: null,
          source: 'unavailable',
          zone_key: null,
          message: tr('Nema aktivne opservacije ili indeksa za pregled.'),
        },
      })
      return
    }
    setInspectPoint({ lat, lng, sample: null, loading: true })
    try {
      const sample = await sampleSatelliteObservation(activeObservation.id, {
        latitude: lat,
        longitude: lng,
        index: activeIndex,
      })
      setInspectPoint({ lat, lng, sample, loading: false })
      if (sample.zone_key) setSelectedZoneKey(sample.zone_key)
    } catch {
      setInspectPoint({
        lat,
        lng,
        loading: false,
        sample: {
          observation_id: activeObservation.id,
          index: activeIndex,
          acquisition_date: activeObservation.acquisition_date,
          longitude: lng,
          latitude: lat,
          value: null,
          source: 'unavailable',
          zone_key: null,
          message: tr('Pregled tačke nije uspeo. Pokušajte ponovo.'),
        },
      })
    }
  }

  const mapShared = parcel
    ? {
        parcel,
        activeIndex,
        availableIndices,
        onActiveIndexChange: setActiveIndex,
        selectedZoneKey,
        onSelectZone: (key: string | null) => setSelectedZoneKey((current) => (current === key ? null : key)),
        onMapInspect: handleMapInspect,
        inspectPoint,
        onClearInspect: () => setInspectPoint(null),
        allowDrawBoundary: true,
        onBoundarySave: (boundary: GeoJSON.Polygon) => boundaryMutation.mutateAsync(boundary),
        boundarySaving: boundaryMutation.isPending,
      }
    : null

  return (
    <div className="mx-auto w-full max-w-6xl space-y-4 pb-16">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link to={`/orchard/${parcelId}`} className="text-sm font-medium text-primary hover:underline">
            ← Nazad na parcelu
          </Link>
          <p className="kicker mt-2">Monitoring</p>
          <h1 className="mt-1 text-xl font-semibold sm:text-2xl">
            {parcel?.name || tr('Parcela')}
            {parcel?.area_hectares ? (
              <span className="ml-2 text-base font-normal text-muted-foreground">
                · {Number(parcel.area_hectares).toFixed(2)} ha
              </span>
            ) : null}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {tr('Status')}: {statusLabel(data?.status, data?.available)}
            {activeObservation?.acquisition_date
              ? tr(' · opservacija {{date}}', { date: activeObservation.acquisition_date })
              : ''}
            {activeObservation?.cloud_cover != null
              ? tr(' · oblačnost {{pct}}%', { pct: fmt(activeObservation.cloud_cover, 0) })
              : ''}
            {capabilities?.sensor ? ` · ${capabilities.sensor}` : data?.provider ? ` · ${data.provider}` : ''}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {(data?.history?.length ?? 0) > 0 ? (
            <label className="flex items-center gap-2 text-sm">
              <span className="text-muted-foreground">{tr('Datum')}</span>
              <select
                className="h-9 rounded-lg border border-border bg-card px-2 text-sm"
                value={selectedObservationId ?? ''}
                onChange={(event) => {
                  setSelectedObservationId(event.target.value)
                  setSelectedZoneKey(null)
                  setInspectPoint(null)
                  setCompareId(null)
                }}
              >
                {(data?.history ?? []).map((row) => (
                  <option key={row.id} value={row.id}>
                    {row.acquisition_date}
                    {row.cloud_cover != null ? ` (${fmt(row.cloud_cover, 0)}% obl.)` : ''}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          <Link to={`/orchard/${parcelId}`}>
            <Button variant="outline" size="sm">
              {tr('Profil parcele')}
            </Button>
          </Link>
          <Button
            variant="outline"
            size="sm"
            disabled={refreshMutation.isPending}
            onClick={() => refreshMutation.mutate()}
          >
            {refreshMutation.isPending ? tr('Obrada…') : tr('Osveži snimak')}
          </Button>
        </div>
      </header>

      {satQuery.isLoading || parcelQuery.isLoading ? (
        <p className="text-sm text-muted-foreground">{tr('Učitavanje…')}</p>
      ) : null}
      {satQuery.isError ? <p className="text-sm text-danger">{tr('Satelitski podaci nisu učitani.')}</p> : null}
      {boundaryMessage ? (
        <p className={`text-sm ${boundaryMutation.isError ? 'text-danger' : 'text-muted-foreground'}`}>
          {boundaryMessage}
        </p>
      ) : null}

      {mapShared && !compareMode ? (
        <ParcelMonitoringMap
          {...mapShared}
          zones={zones}
          indexLayer={indexLayer}
          dateLabel={activeObservation?.acquisition_date ?? null}
        />
      ) : null}

      {mapShared && compareMode && compareQuery.data && activeObservation ? (
        <div className="space-y-2">
          <p className="text-sm font-medium text-foreground">
            {tr('Poređenje snimaka: {{from}} ↔ {{to}}', {
              from: compareQuery.data.acquisition_date,
              to: activeObservation.acquisition_date,
            })}
          </p>
          <p className="text-xs text-muted-foreground">
            {tr('Poređenje koristi agregate iste metode; razlika nije mapa promena po pikselu.')}
          </p>
          <div className="grid gap-3 lg:grid-cols-2">
            <ParcelMonitoringMap
              {...mapShared}
              compactControls
              allowDrawBoundary={false}
              onMapInspect={undefined}
              inspectPoint={null}
              className="h-[min(52vh,480px)]"
              zones={compareQuery.data.zones ?? []}
              indexLayer={compareIndexLayer}
              availableIndices={compareAvailableIndices}
              dateLabel={compareQuery.data.acquisition_date}
            />
            <ParcelMonitoringMap
              {...mapShared}
              compactControls
              allowDrawBoundary={false}
              onMapInspect={undefined}
              inspectPoint={null}
              className="h-[min(52vh,480px)]"
              zones={zones}
              indexLayer={indexLayer}
              dateLabel={activeObservation.acquisition_date}
            />
          </div>
          <Button type="button" size="sm" variant="outline" onClick={() => setCompareId(null)}>
            {tr('Zatvori poređenje')}
          </Button>
        </div>
      ) : null}

      {data?.status === 'boundary_required' || (parcel && !parcel.boundary) ? (
        <ParcelBoundarySetupCard
          parcelId={parcelId}
          parcel={parcel}
          generateAfterSave
          description={tr("Unesite Google Maps link i površinu za približnu granicu, ili nacrtajte tačnu granicu direktno na mapi iznad.")}
          onCompleted={() => {
            autoRefreshAttempted.current = false
          }}
        />
      ) : null}

      {data && !data.available && data.status !== 'boundary_required' ? (
        <Card>
          <CardContent className="space-y-3 py-6">
            <p className="font-medium">{data.message || tr('Nema satelitskih opservacija.')}</p>
            {data.status === 'no_observations' ? (
              <Button
                type="button"
                size="sm"
                disabled={refreshMutation.isPending}
                onClick={() => refreshMutation.mutate()}
              >
                {refreshMutation.isPending ? tr('Povlačenje snimka…') : tr('Generiši satelitski snimak')}
              </Button>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {activeObservation ? (
        <section className="overflow-hidden rounded-2xl border border-border bg-card">
          <div className="flex flex-wrap items-end justify-between gap-3 border-b border-border/70 px-4 py-3">
            <h2 className="text-base font-semibold">{tr('Sažetak opservacije')}</h2>
            {activeObservation.processed_at ? (
              <p className="text-[11px] text-muted-foreground">
                {tr('Obrađeno')}: {new Date(activeObservation.processed_at).toLocaleString('sr-RS')}
              </p>
            ) : null}
          </div>
          <div className="grid divide-y divide-border/70 sm:grid-cols-3 sm:divide-x sm:divide-y-0">
            <IndexSummary
              label="NDVI"
              subtitle={tr("Prosečna bujnost vegetacije")}
              value={fmt(activeObservation.ndvi_mean)}
              range={fmtRange(activeObservation.ndvi_min, activeObservation.ndvi_max)}
              active={activeIndex === 'ndvi'}
              onClick={() => setActiveIndex('ndvi')}
            />
            <IndexSummary
              label="NDRE"
              subtitle={tr("Prosečna „svežina“ krošnje")}
              value={fmt(activeObservation.ndre_mean)}
              range={fmtRange(activeObservation.ndre_min, activeObservation.ndre_max)}
              active={activeIndex === 'ndre'}
              onClick={() => setActiveIndex('ndre')}
            />
            <IndexSummary
              label="NDWI"
              subtitle={tr("Prosečan signal vlage u biljkama")}
              value={fmt(activeObservation.ndwi_mean)}
              range={fmtRange(activeObservation.ndwi_min, activeObservation.ndwi_max)}
              active={activeIndex === 'ndwi'}
              onClick={() => setActiveIndex('ndwi')}
            />
          </div>
        </section>
      ) : null}

      {selectedZone ? (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">
              {tr('{{title}} (prosek zone)', {
                title: zoneTitle(selectedZone.zone_key, selectedZone.tree_public_ids),
              })}
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-2 text-sm sm:grid-cols-3">
            <Metric label="NDVI" value={fmt(selectedZone.ndvi)} />
            <Metric label="NDRE" value={fmt(selectedZone.ndre)} />
            <Metric label="NDWI" value={fmt(selectedZone.ndwi)} />
            <p className="sm:col-span-3 text-xs text-muted-foreground">
              {selectedZone.tree_public_ids?.length
                ? tr('Stabla u ovoj zoni: {{trees}}{{extra}}.', {
                    trees: selectedZone.tree_public_ids.slice(0, 12).join(', '),
                    extra:
                      selectedZone.tree_public_ids.length > 12
                        ? tr(' (+{{count}})', { count: selectedZone.tree_public_ids.length - 12 })
                        : '',
                  })
                : tr('Prosek dela parcele — nije jedno stablo ni Sentinel piksel.')}
            </p>
          </CardContent>
        </Card>
      ) : null}

      <SatelliteHistoryPanel parcelId={parcelId} />

      {(data?.history?.length ?? 0) > 1 ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{tr('Istorija opservacija')}</CardTitle>
            <p className="text-sm text-muted-foreground">
              {tr('Datum birate i iznad mape. „Uporedi“ prikazuje agregate dve stvarne opservacije.')}
            </p>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full min-w-[32rem] text-left text-sm">
              <thead className="text-xs uppercase tracking-wide text-muted-foreground">
                <tr className="border-b border-border">
                  <th className="py-2">{tr('Datum')}</th>
                  <th className="py-2 text-right">NDVI</th>
                  <th className="py-2 text-right">NDRE</th>
                  <th className="py-2 text-right">NDWI</th>
                  <th className="py-2 text-right">{tr('Oblačnost')}</th>
                  <th className="py-2 text-right">{tr('Uporedi')}</th>
                </tr>
              </thead>
              <tbody>
                {(data?.history ?? []).map((row) => {
                  const active = selectedObservationId === row.id
                  const comparing = compareId === row.id
                  return (
                    <tr
                      key={row.id}
                      className={`border-b border-border/70 last:border-0 ${active ? 'bg-primary/5' : ''}`}
                    >
                      <td className="py-2">
                        <button
                          type="button"
                          className="font-medium text-primary hover:underline"
                          onClick={() => {
                            setSelectedObservationId(row.id)
                            setSelectedZoneKey(null)
                            setInspectPoint(null)
                          }}
                        >
                          {row.acquisition_date}
                          {active ? tr(' · aktivno') : ''}
                        </button>
                      </td>
                      <td className="py-2 text-right font-mono">{fmt(row.ndvi_mean)}</td>
                      <td className="py-2 text-right font-mono">{fmt(row.ndre_mean)}</td>
                      <td className="py-2 text-right font-mono">{fmt(row.ndwi_mean)}</td>
                      <td className="py-2 text-right font-mono">
                        {row.cloud_cover != null ? `${fmt(row.cloud_cover, 0)}%` : '—'}
                      </td>
                      <td className="py-2 text-right">
                        <button
                          type="button"
                          className="text-xs font-medium text-muted-foreground hover:text-foreground hover:underline"
                          disabled={row.id === selectedObservationId}
                          onClick={() => setCompareId(comparing ? null : row.id)}
                        >
                          {comparing ? tr('Ukloni') : tr('Izaberi')}
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </CardContent>
        </Card>
      ) : null}

      {anomalyBriefing ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{tr('Gde da obratite pažnju')}</CardTitle>
            <p className="text-sm text-muted-foreground">
              {tr('Satelit pokazuje slabije delove zasada. Nije dijagnoza — samo gde da prvo odete.')}
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="rounded-xl border border-border bg-muted/20 px-4 py-3">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                {tr('Lokacija')}
              </p>
              <p className="mt-1 text-base font-semibold first-letter:uppercase">
                {anomalyBriefing.locationLabel}
              </p>
            </div>

            <BriefingBlock label={tr("Šta se vidi na snimku")} text={anomalyBriefing.observed} />
            <BriefingBlock label={tr("Šta to konkretno znači")} text={anomalyBriefing.meaning} />
            <BriefingBlock label={tr("Zašto je to važno")} text={anomalyBriefing.impact} />

            <div>
              <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                {tr('Šta da uradite')}
              </p>
              <ol className="mt-2 list-decimal space-y-1.5 pl-4 text-sm">
                {anomalyBriefing.actions.map((action) => (
                  <li key={action}>{action}</li>
                ))}
              </ol>
            </div>

            <Link
              to={`/health/new?parcelId=${parcelId}&returnTo=${encodeURIComponent(`/orchard/${parcelId}/satellite`)}`}
            >
              <Button type="button" size="sm">
                {tr('Prijavi problem')}
              </Button>
            </Link>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{tr('Kako da čitate boje na mapi')}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-muted-foreground">
          <p>
            {tr(
              'Žuta linija je granica parcele. Boje unutra pokazuju kako biljke izgledaju sa satelita tog dana.',
            )}
          </p>
          <div className="space-y-2">
            <p>
              <strong className="font-medium text-foreground">NDVI</strong> —{' '}
              {tr(
                'Gledajte žute, narandžaste i crvene delove — tu sadnice izgledaju slabije ili sitnije. Zelenije = bujnije i jače. Fokus na slabije delove, ne na zelene.',
              )}
            </p>
            <p>
              <strong className="font-medium text-foreground">NDRE</strong> —{' '}
              {tr(
                'Isto kao NDVI, malo osetljivije. Narandžasto/crveno = slabiji deo zasada; zeleno = jači. Prvo obiđite slabije delove.',
              )}
            </p>
            <p>
              <strong className="font-medium text-foreground">NDWI</strong> —{' '}
              {tr(
                'Narandžasto/crvenije može značiti da biljke deluju suvlje. Nije mera zalivanja — samo signal gde da proverite prvo.',
              )}
            </p>
          </div>
          <p>
            {tr(
              'Satelit ne vidi svako stablo — vidi šire delove parcele. Brojevi iznad su prosek cele parcele za taj dan.',
            )}
          </p>
        </CardContent>
      </Card>

      {refreshMutation.isError ? (
        <p className="text-sm text-danger">{tr('Osvežavanje nije uspelo. Prethodni podaci ostaju dostupni.')}</p>
      ) : null}
      {refreshMutation.data?.message && refreshMutation.data.status !== 'completed' ? (
        <p className="text-sm text-muted-foreground">{refreshMutation.data.message}</p>
      ) : null}
    </div>
  )
}

function fmtRange(min: string | null | undefined, max: string | null | undefined) {
  if (min == null && max == null) return null
  return `${fmt(min)} – ${fmt(max)}`
}

function BriefingBlock({ label, text }: { label: string; text: string }) {
  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className="mt-1 text-sm leading-relaxed">{text}</p>
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="font-mono text-sm font-semibold">{value}</p>
    </div>
  )
}

function IndexSummary({
  label,
  subtitle,
  value,
  range,
  active,
  onClick,
}: {
  label: string
  subtitle: string
  value: string
  range: string | null
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-4 py-3 text-left transition-colors hover:bg-muted/40 ${active ? 'bg-primary/5' : ''}`}
    >
      <div className="flex items-baseline justify-between gap-2">
        <p className="text-sm font-semibold text-foreground">{label}</p>
        {active ? <p className="text-[10px] font-medium text-primary">{tr('na mapi')}</p> : null}
      </div>
      <p className="mt-1 font-mono text-xl font-semibold tracking-tight text-foreground">{value}</p>
      {range ? <p className="mt-0.5 text-xs text-muted-foreground">opseg {range}</p> : null}
      <p className="mt-1 text-[10px] leading-snug text-muted-foreground">{subtitle}</p>
    </button>
  )
}
