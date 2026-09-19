import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { deleteParcel, listParcels } from '@/features/orchard/api'
import { formatNumber } from '@/shared/lib/format'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardHeader } from '@/shared/ui/card'

export function OrchardIndexPage() {
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
          <p className="kicker">Zasadi</p>
          <h1 className="mt-1 text-xl font-semibold sm:text-2xl">Parcele voćnjaka</h1>
        </div>
        <Link to="/orchard/new">
          <Button>Nova parcela</Button>
        </Link>
      </div>

      {parcelsQuery.isLoading ? (
        <p className="text-sm text-muted-foreground">Učitavanje parcela…</p>
      ) : parcels.length === 0 ? (
        <Card>
          <CardContent className="py-10 text-sm text-muted-foreground">
            Još nema parcela. Napravite pravougaoni voćnjak da otvorite zasad.
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
                {parcel.maps_url ? (
                  <a
                    href={parcel.maps_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex text-sm font-medium text-primary hover:underline"
                  >
                    Otvori na Google Maps
                  </a>
                ) : (
                  <p className="text-sm text-muted-foreground">Google Maps link nije unet.</p>
                )}
                <dl className="grid grid-cols-3 gap-2 text-sm sm:gap-3">
                  <div>
                    <dt className="text-muted-foreground">Redovi</dt>
                    <dd className="font-mono">{parcel.row_count ?? '—'}</dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">Stabla</dt>
                    <dd className="font-mono">{formatNumber(parcel.tree_count)}</dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">Površina</dt>
                    <dd className="font-mono">
                      {parcel.area_hectares ? `${Number(parcel.area_hectares).toFixed(2)} ha` : '—'}
                    </dd>
                  </div>
                </dl>
                <div className="flex flex-wrap gap-2">
                  <Link to={`/orchard/${parcel.id}`}>
                    <Button size="sm">Otvori mapu</Button>
                  </Link>
                  <Link to={`/orchard/${parcel.id}/production`}>
                    <Button size="sm" variant="outline">
                      Proizvodnja
                    </Button>
                  </Link>
                  <Link to={`/orchard/${parcel.id}/report`}>
                    <Button size="sm" variant="outline">
                      Izveštaj
                    </Button>
                  </Link>
                  <Link to={`/orchard/${parcel.id}/edit`}>
                    <Button size="sm" variant="outline">
                      Izmeni
                    </Button>
                  </Link>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={deleteMutation.isPending}
                    onClick={() => {
                      if (!window.confirm(`Obrisati ${parcel.name}? Zasad i svi zapisi na parceli biće uklonjeni.`)) {
                        return
                      }
                      deleteMutation.mutate(parcel.id)
                    }}
                  >
                    Obriši
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
      {deleteMutation.error ? (
        <p className="text-sm text-danger">
          {deleteMutation.error instanceof Error ? deleteMutation.error.message : 'Brisanje nije uspelo'}
        </p>
      ) : null}
    </div>
  )
}
