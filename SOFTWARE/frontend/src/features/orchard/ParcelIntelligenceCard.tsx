import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { getParcelIntelligence, requestParcelIntelligence } from '@/features/orchard/api'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'

import { tr } from '@/shared/i18n/i18n'
export function ParcelIntelligenceCard({ parcelId }: { parcelId: string }) {
  const queryClient = useQueryClient()
  const query = useQuery({
    queryKey: ['parcel-intelligence', parcelId],
    queryFn: () => getParcelIntelligence(parcelId),
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
  })
  const analyze = useMutation({
    mutationFn: () => requestParcelIntelligence(parcelId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['parcel-intelligence', parcelId] })
    },
  })

  const data = query.data
  const active = data?.active_alerts ?? []

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-3 space-y-0 px-4 py-3">
        <CardTitle className="text-base">AgroTwin Intelligence</CardTitle>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={analyze.isPending}
            onClick={() => analyze.mutate()}
          >
            {analyze.isPending ? 'Analiza…' : 'Analiziraj'}
          </Button>
          <Link to={`/orchard/${parcelId}/intelligence`}>
            <Button variant="outline" size="sm">
              Detalji
            </Button>
          </Link>
        </div>
      </CardHeader>
      <CardContent className="space-y-3 px-4 py-3">
        {query.isLoading ? <div className="h-14 animate-pulse rounded-lg bg-muted" /> : null}
        {query.isError ? (
          <p className="text-xs text-muted-foreground">Intelligence podaci trenutno nisu dostupni.</p>
        ) : null}

        {data ? (
          <>
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
              <span>Aktivni alerti: {active.length}</span>
              <span>
                Poslednja analiza:{' '}
                {data.last_analysis?.started_at
                  ? new Date(data.last_analysis.started_at).toLocaleString('sr-RS')
                  : '—'}
              </span>
              {data.last_analysis && !data.last_analysis.ai_called ? (
                <span>AI nije pozvan ({data.last_analysis.skip_reason || tr('nema promena')})</span>
              ) : null}
            </div>

            {active.length === 0 ? (
              <p className="text-sm text-muted-foreground">{tr('Nema aktivnih upozorenja.')}</p>
            ) : (
              <ul className="space-y-2">
                {active.slice(0, 3).map((alert) => {
                  const trees = alert.evidence?.tree_public_ids ?? []
                  const zones = alert.evidence?.zone_keys ?? []
                  const indices = alert.evidence?.affected_indices ?? []
                  const place =
                    trees.length > 0
                      ? trees.slice(0, 4).join(', ') + (trees.length > 4 ? ` (+${trees.length - 4})` : '')
                      : zones.length
                        ? `${zones.length} mesta`
                        : null
                  return (
                    <li key={alert.id} className="rounded-lg border border-border px-3 py-2">
                      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                        {alert.severity}
                        {alert.evidence?.observation_date
                          ? ` · ${alert.evidence.observation_date}`
                          : ''}
                      </p>
                      <p className="text-sm font-medium">{alert.title}</p>
                      <p className="mt-1 text-xs text-muted-foreground">{alert.summary}</p>
                      {place || indices.length ? (
                        <p className="mt-1 text-[11px] text-muted-foreground">
                          {place}
                          {place && indices.length ? ' · ' : null}
                          {indices.length
                            ? indices.map((item) => item.toUpperCase()).join(', ')
                            : null}
                        </p>
                      ) : null}
                    </li>
                  )
                })}
              </ul>
            )}
          </>
        ) : null}
      </CardContent>
    </Card>
  )
}
