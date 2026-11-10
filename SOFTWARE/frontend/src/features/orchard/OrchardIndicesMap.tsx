import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  getParcelSatelliteMonitoring,
  refreshParcelSatellite,
} from '@/features/orchard/api'
import {
  ParcelMonitoringMap,
  type IndexLayerId,
} from '@/features/orchard/monitoring/ParcelMonitoringMap'
import type { OrchardTwin, SatelliteObservation, VisualizationLayer } from '@/shared/api/types'
import { Button } from '@/shared/ui/button'

import { tr } from '@/shared/i18n/i18n'
function pickIndexLayer(
  observation: SatelliteObservation | null | undefined,
  index: IndexLayerId,
): VisualizationLayer | null {
  if (!observation) return null
  const match = (observation.visualization_layers ?? []).find((layer) => layer.index === index)
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

type Props = {
  parcelId: string
  twin: OrchardTwin
}

export function OrchardIndicesMap({ parcelId, twin }: Props) {
  const queryClient = useQueryClient()
  const [activeIndex, setActiveIndex] = useState<IndexLayerId | null>('ndvi')
  const autoRefreshAttempted = useRef(false)

  const satQuery = useQuery({
    queryKey: ['parcel-satellite', parcelId],
    queryFn: () => getParcelSatelliteMonitoring(parcelId),
    staleTime: 10 * 60 * 1000,
  })

  const refreshMutation = useMutation({
    mutationFn: () => refreshParcelSatellite(parcelId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['parcel-satellite', parcelId] })
    },
  })

  const latest = satQuery.data?.latest ?? null
  const availableIndices = useMemo(() => availableIndexLayers(latest), [latest])
  const indexLayer = activeIndex ? pickIndexLayer(latest, activeIndex) : null

  useEffect(() => {
    autoRefreshAttempted.current = false
  }, [parcelId])

  // Boundary + geo exist → auto-fetch first Sentinel-2 observation (NDVI/NDRE/NDWI).
  useEffect(() => {
    if (autoRefreshAttempted.current) return
    if (!satQuery.data || satQuery.data.available) return
    if (satQuery.data.status !== 'no_observations') return
    if (!twin.parcel.boundary) return
    autoRefreshAttempted.current = true
    refreshMutation.mutate()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [satQuery.data?.status, satQuery.data?.available, twin.parcel.boundary])

  useEffect(() => {
    if (availableIndices.length === 0) return
    if (activeIndex && availableIndices.includes(activeIndex)) return
    setActiveIndex(availableIndices.includes('ndvi') ? 'ndvi' : availableIndices[0] ?? null)
  }, [availableIndices, activeIndex])

  if (satQuery.isLoading || refreshMutation.isPending) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 bg-muted/40 px-4 text-center">
        <p className="text-sm font-medium text-foreground">
          {refreshMutation.isPending ? tr('Generisanje satelitskih indeksa…') : tr('Učitavanje indeksa…')}
        </p>
        {refreshMutation.isPending ? (
          <p className="text-xs text-muted-foreground">{tr('NDVI, NDRE i NDWI za granicu parcele')}</p>
        ) : null}
      </div>
    )
  }

  if (satQuery.isError) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 bg-muted/40 px-4 text-center">
        <p className="text-sm text-muted-foreground">{tr('Satelitski indeksi trenutno nisu dostupni.')}</p>
        <Link to={`/orchard/${parcelId}/satellite`} className="text-sm font-medium text-primary hover:underline">
          Otvori detaljni monitoring
        </Link>
      </div>
    )
  }

  const data = satQuery.data
  if (!data?.available || !latest) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 bg-muted/40 px-4 text-center">
        <div>
          <p className="text-sm font-medium text-foreground">{tr('Nema aktivnog snimka')}</p>
          <p className="mt-1 text-xs text-muted-foreground">
            {data?.message ?? tr('Generišite Sentinel-2 opservaciju da vidite NDVI, NDRE i NDWI.')}
          </p>
        </div>
        {data?.status === 'no_observations' || data?.status === 'ok' ? (
          <Button
            size="sm"
            disabled={refreshMutation.isPending}
            onClick={() => refreshMutation.mutate()}
          >
            {refreshMutation.isPending ? tr('Generisanje…') : tr('Pokušaj ponovo')}
          </Button>
        ) : (
          <Link to={`/orchard/${parcelId}/satellite`}>
            <Button size="sm" variant="outline">
              Podesi monitoring
            </Button>
          </Link>
        )}
        {refreshMutation.isError ? (
          <p className="text-xs text-danger">{tr('Generisanje nije uspelo. Pokušajte ponovo.')}</p>
        ) : null}
      </div>
    )
  }

  return (
    <ParcelMonitoringMap
      embedded
      parcel={twin.parcel}
      zones={[]}
      indexLayer={indexLayer}
      activeIndex={activeIndex}
      availableIndices={availableIndices}
      showZones={false}
      onActiveIndexChange={setActiveIndex}
      selectedZoneKey={null}
      onSelectZone={() => undefined}
      dateLabel={latest.acquisition_date}
      className="h-full"
    />
  )
}
