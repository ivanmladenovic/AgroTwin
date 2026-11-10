import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'

import { getParcelLabor } from '@/features/workforce/api'
import { formatDate, formatMoney, formatNumber } from '@/shared/lib/format'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'
import { tr } from '@/shared/i18n/i18n'

export function ParcelLaborCard({ parcelId }: { parcelId: string }) {
  const laborQuery = useQuery({
    queryKey: ['parcel-labor', parcelId],
    queryFn: () => getParcelLabor(parcelId),
  })

  const summary = laborQuery.data
  const recent = summary?.recent_tasks ?? []

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-3 space-y-0 px-4 py-3">
        <CardTitle className="text-base">Rad</CardTitle>
        <Link to={`/costs/workforce?parcelId=${parcelId}`}>
          <Button variant="outline" size="sm">
            Otvori
          </Button>
        </Link>
      </CardHeader>
      <CardContent className="space-y-3 px-4 py-3">
        {laborQuery.isLoading ? (
          <div className="h-16 animate-pulse rounded-lg bg-muted" />
        ) : laborQuery.isError ? (
          <p className="text-xs text-muted-foreground">Podaci o radu trenutno nisu dostupni.</p>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <p className="text-xs text-muted-foreground">Ukupno sati</p>
                <p className="text-lg font-semibold">{formatNumber(Number(summary?.total_hours ?? 0))}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">{tr('Ukupan trošak')}</p>
                <p className="text-lg font-semibold">{formatMoney(summary?.total_labor_cost)}</p>
              </div>
            </div>
            <div className="space-y-2">
              <p className="text-xs font-medium text-muted-foreground">Nedavni zadaci</p>
              {recent.length === 0 ? (
                <p className="text-xs text-muted-foreground">{tr('Nema evidentiranog rada na ovoj parceli.')}</p>
              ) : (
                recent.slice(0, 5).map((task) => (
                  <div key={task.id} className="flex items-start justify-between gap-2 text-sm">
                    <div className="min-w-0">
                      <p className="truncate font-medium">
                        {task.task_type?.name ?? 'Zadatak'} · {task.worker_name ?? 'Radnik'}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {formatDate(task.worked_on)} · {formatNumber(Number(task.hours))} h
                      </p>
                    </div>
                    <p className="shrink-0 font-medium">{formatMoney(task.labor_cost)}</p>
                  </div>
                ))
              )}
            </div>
            <Link
              to={`/costs/workforce?parcelId=${parcelId}`}
              className="inline-flex text-xs font-medium text-primary hover:underline"
            >
              Dodaj zadatak
            </Link>
          </>
        )}
      </CardContent>
    </Card>
  )
}
