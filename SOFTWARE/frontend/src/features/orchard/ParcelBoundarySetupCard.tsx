import { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'

import { refreshParcelSatellite, updateParcel, warmParcelEnvironment } from '@/features/orchard/api'
import type { Parcel } from '@/shared/api/types'
import { ApiError } from '@/shared/lib/api'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'

import { tr } from '@/shared/i18n/i18n'
type Props = {
  parcelId: string
  parcel: Parcel | null | undefined
  /** When true, after saving location also POST satellite/refresh. */
  generateAfterSave?: boolean
  title?: string
  description?: string
  onCompleted?: (result: { boundaryReady: boolean; satelliteStatus?: string }) => void
}

export function ParcelBoundarySetupCard({
  parcelId,
  parcel,
  generateAfterSave = true,
  title = tr('Lokacija i granica parcele'),
  description = tr('Unesite Google Maps link i površinu. Sistem pravi približnu granicu (kvadrat oko pin-a), zatim povlači Sentinel-2 snimak.'),
  onCompleted,
}: Props) {
  const queryClient = useQueryClient()
  const [mapsUrl, setMapsUrl] = useState('')
  const [areaHa, setAreaHa] = useState('')
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => {
    if (!parcel) return
    setMapsUrl(parcel.maps_url ?? '')
    setAreaHa(parcel.area_hectares != null ? String(parcel.area_hectares) : '')
  }, [parcel])

  const mutation = useMutation({
    mutationFn: async () => {
      const area = Number(areaHa.replace(',', '.'))
      if (!Number.isFinite(area) || area <= 0) {
        throw new Error(tr('Unesite površinu u hektarima (veću od nule).'))
      }
      const url = mapsUrl.trim()
      if (!url) {
        throw new Error(tr('Unesite Google Maps link zasada.'))
      }
      const updated = await updateParcel(parcelId, {
        maps_url: url,
        area_hectares: area,
      })
      const boundaryReady = Boolean(updated.boundary)
      if (!boundaryReady) {
        return {
          boundaryReady: false,
          satelliteStatus: undefined as string | undefined,
          message:
            tr('Lokacija je sačuvana, ali granica nije napravljena. Proverite da je Maps link validan (pin na parceli).'),
        }
      }
      if (!generateAfterSave) {
        return {
          boundaryReady: true,
          satelliteStatus: undefined,
          message: tr('Približna granica je postavljena.'),
        }
      }
      const sync = await refreshParcelSatellite(parcelId)
      return {
        boundaryReady: true,
        satelliteStatus: sync.status,
        message:
          sync.status === 'completed'
            ? tr('Granica je postavljena i satelitski snimak je obrađen.')
            : sync.status === 'skipped' && sync.skipped_duplicate
              ? tr('Granica je postavljena. Snimak za ovaj datum već postoji.')
              : sync.message ||
                (sync.status === 'skipped'
                  ? tr('Granica je postavljena. Trenutno nema pogodnog Sentinel-2 snimka u prozoru pretrage.')
                  : tr('Granica je postavljena. Status snimka: {{status}}.', { status: sync.status })),
      }
    },
    onSuccess: async (result) => {
      setMessage(result.message)
      await queryClient.invalidateQueries({ queryKey: ['parcel', parcelId] })
      await queryClient.invalidateQueries({ queryKey: ['parcels'] })
      await queryClient.invalidateQueries({ queryKey: ['orchard-twin', parcelId] })
      await queryClient.invalidateQueries({ queryKey: ['parcel-satellite', parcelId] })
      void warmParcelEnvironment(parcelId).then(() => {
        void queryClient.invalidateQueries({ queryKey: ['parcel-weather', parcelId] })
        void queryClient.invalidateQueries({ queryKey: ['parcel-soil', parcelId] })
      })
      onCompleted?.({
        boundaryReady: result.boundaryReady,
        satelliteStatus: result.satelliteStatus,
      })
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        setMessage(error.message)
        return
      }
      setMessage(error instanceof Error ? error.message : tr('Čuvanje nije uspelo.'))
    },
  })

  const hasBoundary = Boolean(parcel?.boundary)
  const hasPin = parcel?.latitude != null && parcel?.longitude != null

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">{title}</CardTitle>
        <p className="text-sm text-muted-foreground">{description}</p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
          <span>
            {tr('Pin:')}{' '}
            <strong className="font-medium text-foreground">{hasPin ? tr('postoji') : tr('nedostaje')}</strong>
          </span>
          <span>
            {tr('Granica:')}{' '}
            <strong className="font-medium text-foreground">
              {hasBoundary ? tr('postoji') : tr('nedostaje')}
            </strong>
          </span>
          {parcel?.area_hectares != null ? (
            <span>
              {tr('Površina: {{area}} ha', {
                area: Number(parcel.area_hectares).toLocaleString('sr-RS', { maximumFractionDigits: 2 }),
              })}
            </span>
          ) : null}
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor={`maps-url-${parcelId}`}>{tr('Google Maps link')}</Label>
            <Input
              id={`maps-url-${parcelId}`}
              type="url"
              placeholder="https://maps.app.goo.gl/…"
              value={mapsUrl}
              onChange={(event) => setMapsUrl(event.target.value)}
              disabled={mutation.isPending}
            />
            <p className="text-[11px] text-muted-foreground">
              {tr('U Google Maps: otvorite zasad → Deli → Kopiraj link.')}
            </p>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={`area-ha-${parcelId}`}>{tr('Površina (ha)')}</Label>
            <Input
              id={`area-ha-${parcelId}`}
              type="number"
              step="0.0001"
              min="0.0001"
              value={areaHa}
              onChange={(event) => setAreaHa(event.target.value)}
              disabled={mutation.isPending}
            />
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            disabled={mutation.isPending}
            onClick={() => {
              setMessage(null)
              mutation.mutate()
            }}
          >
            {mutation.isPending
              ? generateAfterSave
                ? tr('Čuvanje i obrada snimka…')
                : tr('Čuvanje…')
              : generateAfterSave
                ? hasBoundary
                  ? tr('Ažuriraj granicu i osveži snimak')
                  : tr('Postavi granicu i generiši snimak')
                : tr('Sačuvaj lokaciju')}
          </Button>
        </div>

        {message ? <p className="text-sm text-muted-foreground">{message}</p> : null}
      </CardContent>
    </Card>
  )
}
