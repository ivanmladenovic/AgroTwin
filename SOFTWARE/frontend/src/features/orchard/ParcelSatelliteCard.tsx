import { useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { getParcelSatelliteMonitoring, refreshParcelSatellite } from '@/features/orchard/api'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'
import { tr } from '@/shared/i18n/i18n'

function formatIndex(value: string | null | undefined) {
  if (value == null || value === '') return '—'
  const numeric = Number(value)
  if (Number.isNaN(numeric)) return '—'
  return numeric.toLocaleString('sr-RS', { maximumFractionDigits: 3 })
}

export function ParcelSatelliteCard({ parcelId }: { parcelId: string }) {
  const queryClient = useQueryClient()
  const autoRefreshAttempted = useRef(false)
  const query = useQuery({
    queryKey: ['parcel-satellite', parcelId],
    queryFn: () => getParcelSatelliteMonitoring(parcelId),
    staleTime: 10 * 60 * 1000,
    refetchOnWindowFocus: false,
  })

  const refreshMutation = useMutation({
    mutationFn: () => refreshParcelSatellite(parcelId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['parcel-satellite', parcelId] })
    },
  })

  useEffect(() => {
    autoRefreshAttempted.current = false
  }, [parcelId])

  useEffect(() => {
    if (autoRefreshAttempted.current) return
    if (!query.data || query.data.available) return
    if (query.data.status !== 'no_observations') return
    autoRefreshAttempted.current = true
    refreshMutation.mutate()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query.data?.status, query.data?.available])

  const data = query.data

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-3 space-y-0 px-4 py-3">
        <CardTitle className="text-base">{tr('Satelitski monitoring')}</CardTitle>
        <Link to={`/orchard/${parcelId}/satellite`}>
          <Button variant="outline" size="sm">
            {tr('Detalji')}
          </Button>
        </Link>
      </CardHeader>
      <CardContent className="space-y-3 px-4 py-3">
        {query.isLoading || refreshMutation.isPending ? (
          <div className="space-y-2">
            <div className="h-16 animate-pulse rounded-lg bg-muted" />
            {refreshMutation.isPending ? (
              <p className="text-xs text-muted-foreground">{tr("Generisanje satelitskih indeksa…")}</p>
            ) : null}
          </div>
        ) : null}

        {query.isError ? (
          <p className="text-xs text-muted-foreground">{tr('Satelitski podaci trenutno nisu dostupni.')}</p>
        ) : null}

        {data && !data.available && !refreshMutation.isPending ? (
          <div className="space-y-2">
            <p className="text-sm font-medium">{tr('Nema aktivnog snimka')}</p>
            <p className="text-xs text-muted-foreground">{data.message}</p>
            {data.status === 'boundary_required' ? (
              <Link to={`/orchard/${parcelId}/satellite`}>
                <Button size="sm" className="mt-1">
                  {tr("Postavi granicu i generiši snimak")}
                </Button>
              </Link>
            ) : data.status === 'no_observations' ? (
              <Button
                size="sm"
                className="mt-1"
                disabled={refreshMutation.isPending}
                onClick={() => refreshMutation.mutate()}
              >
                {tr("Pokušaj ponovo")}
              </Button>
            ) : (
              <Link
                to={`/orchard/${parcelId}/satellite`}
                className="inline-flex text-xs font-medium text-primary hover:underline"
              >
                {tr('Otvori mapu monitoringa')}
              </Link>
            )}
            {refreshMutation.isError ? (
              <p className="text-xs text-danger">{tr('Generisanje nije uspelo. Pokušajte ponovo.')}</p>
            ) : null}
          </div>
        ) : null}

        {data?.available && data.latest ? (
          <div className="space-y-3">
            <div className="grid grid-cols-3 gap-2 text-center">
              <Metric label="NDVI" value={formatIndex(data.latest.ndvi_mean)} />
              <Metric label="NDRE" value={formatIndex(data.latest.ndre_mean)} />
              <Metric label="NDWI" value={formatIndex(data.latest.ndwi_mean)} />
            </div>
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
              <span>
                {tr('Datum snimka: {{date}}', { date: data.latest.acquisition_date })}
              </span>
              <Link to={`/orchard/${parcelId}/satellite`} className="font-medium text-primary hover:underline">
                {tr('Istorija indeksa')}
              </Link>
              <span>
                {tr('Oblačnost:')}{' '}
                {data.latest.cloud_cover != null
                  ? `${Number(data.latest.cloud_cover).toLocaleString('sr-RS', { maximumFractionDigits: 0 })}%`
                  : '—'}
              </span>
              <span>{tr('Anomalije: {{count}}', { count: data.latest.anomaly_count })}</span>
              {data.changes[0]?.change_percent != null ? (
                <span>
                  Δ NDVI: {Number(data.changes[0].change_percent) > 0 ? '+' : ''}
                  {Number(data.changes[0].change_percent).toLocaleString('sr-RS', {
                    maximumFractionDigits: 1,
                  })}
                  %
                </span>
              ) : null}
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-muted/60 px-2 py-2">
      <p className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-0.5 font-mono text-sm font-semibold">{value}</p>
    </div>
  )
}
