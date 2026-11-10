import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { deleteParcel, listParcels } from '@/features/orchard/api'
import { formatNumber } from '@/shared/lib/format'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardHeader } from '@/shared/ui/card'
import { tr } from '@/shared/i18n/i18n'

export function OrchardIndexPage() {
  const { i18n } = useTranslation()
  void i18n.language
  const queryClient = useQueryClient()
  const parcelsQuery = useQuery({ queryKey: ['parcels'], queryFn: listParcels })
  const parcels = parcelsQuery.data ?? []
  const deleteMutation = useMutation({
    mutationFn: deleteParcel,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['parcels'] })
    },
  })

  return (
    <div className="w-full space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="kicker">{tr('Zasadi')}</p>
          <h1 className="mt-1 text-xl font-semibold sm:text-2xl">{tr('Parcele voćnjaka')}</h1>
        </div>
        <Link to="/orchard/new">
          <Button>{tr('Nova parcela')}</Button>
        </Link>
      </div>

      {parcelsQuery.isLoading ? (
        <p className="text-sm text-muted-foreground">{tr('Učitavanje parcela…')}</p>
      ) : parcels.length === 0 ? (
        <Card>
          <CardContent className="py-10 text-sm text-muted-foreground">
            {tr('Još nema parcela. Napravite pravougaoni voćnjak da otvorite zasad.')}
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {parcels.map((parcel) => (
            <Card key={parcel.id} className="h-full">
              <CardHeader>
                <h2 className="text-xl font-medium">{parcel.code}</h2>
              </CardHeader>
              <CardContent className="space-y-4">
                {parcel.code === parcel.name ? null : (
                  <p className="text-sm text-muted-foreground">{parcel.name}</p>
                )}
                <div className="flex flex-wrap items-center justify-between gap-2">
                  {parcel.maps_url ? (
                    <a
                      href={parcel.maps_url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex text-sm font-medium text-primary hover:underline"
                    >
                      {tr('Otvori na Google Maps')}
                    </a>
                  ) : (
                    <p className="text-sm text-muted-foreground">{tr('Google Maps link nije unet.')}</p>
                  )}
                  <Link to={`/orchard/${parcel.id}`} className="shrink-0">
                    <Button size="sm" className="h-9 px-3 text-xs sm:h-10">
                      {tr('Otvori zasad')}
                    </Button>
                  </Link>
                </div>
                <dl className="grid grid-cols-3 gap-2 text-sm sm:gap-3">
                  <div>
                    <dt className="text-muted-foreground">{tr('Redovi')}</dt>
                    <dd className="font-mono">{parcel.row_count ?? '—'}</dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">{tr('Stabla')}</dt>
                    <dd className="font-mono">{formatNumber(parcel.tree_count)}</dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">{tr('Površina')}</dt>
                    <dd className="font-mono">
                      {parcel.area_hectares ? `${Number(parcel.area_hectares).toFixed(2)} ha` : '—'}
                    </dd>
                  </div>
                </dl>
                <div className="grid grid-cols-4 gap-1.5">
                  <Link to={`/orchard/${parcel.id}/production`} className="min-w-0">
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-9 w-full px-1 text-[11px] sm:h-10 sm:px-3 sm:text-xs"
                    >
                      {tr('Proizvodnja')}
                    </Button>
                  </Link>
                  <Link to={`/orchard/${parcel.id}/report`} className="min-w-0">
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-9 w-full px-1 text-[11px] sm:h-10 sm:px-3 sm:text-xs"
                    >
                      {tr('Izveštaj')}
                    </Button>
                  </Link>
                  <Link to={`/orchard/${parcel.id}/edit`} className="min-w-0">
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-9 w-full px-1 text-[11px] sm:h-10 sm:px-3 sm:text-xs"
                    >
                      {tr('Izmeni')}
                    </Button>
                  </Link>
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-9 min-w-0 w-full px-1 text-[11px] sm:h-10 sm:px-3 sm:text-xs"
                    disabled={deleteMutation.isPending}
                    onClick={() => {
                      if (
                        !window.confirm(
                          tr('Obrisati {{name}}? Zasad i svi zapisi na parceli biće uklonjeni.', { name: parcel.name }),
                        )
                      ) {
                        return
                      }
                      deleteMutation.mutate(parcel.id)
                    }}
                  >
                    {tr('Obriši')}
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
      {deleteMutation.error ? (
        <p className="text-sm text-danger">
          {deleteMutation.error instanceof Error ? deleteMutation.error.message : tr('Brisanje nije uspelo')}
        </p>
      ) : null}
    </div>
  )
}
