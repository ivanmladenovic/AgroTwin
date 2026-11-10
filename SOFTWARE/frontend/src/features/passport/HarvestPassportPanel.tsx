import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createHarvestLot,
  finalizeHarvestLot,
  getLotForHarvest,
  publicPassportQrUrl,
  restoreHarvestLot,
  revokeHarvestLot,
} from '@/features/passport/api'
import { PassportFacts } from '@/features/passport/PassportFacts'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'
import { Label } from '@/shared/ui/label'

import { tr } from '@/shared/i18n/i18n'
export function HarvestPassportPanel({ harvestId }: { harvestId: string }) {
  const queryClient = useQueryClient()
  const [allowIndexing, setAllowIndexing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const lotQuery = useQuery({
    queryKey: ['harvest-lot', harvestId],
    queryFn: () => getLotForHarvest(harvestId),
    staleTime: 0,
    refetchOnMount: 'always',
  })

  const lot = lotQuery.data ?? null

  const invalidate = async () => {
    await queryClient.invalidateQueries({ queryKey: ['harvest-lot', harvestId] })
  }

  const createMutation = useMutation({
    mutationFn: () =>
      createHarvestLot({
        harvest_id: harvestId,
        allow_indexing: allowIndexing,
        finalize: false,
      }),
    onSuccess: async () => {
      setError(null)
      await invalidate()
    },
    onError: (err: Error) => setError(err.message),
  })

  const finalizeMutation = useMutation({
    mutationFn: () => finalizeHarvestLot(lot!.id),
    onSuccess: async () => {
      setError(null)
      await invalidate()
    },
    onError: (err: Error) => setError(err.message),
  })

  const revokeMutation = useMutation({
    mutationFn: () => revokeHarvestLot(lot!.id),
    onSuccess: async () => {
      setError(null)
      await invalidate()
    },
    onError: (err: Error) => setError(err.message),
  })

  const restoreMutation = useMutation({
    mutationFn: () => restoreHarvestLot(lot!.id),
    onSuccess: async () => {
      setError(null)
      await invalidate()
    },
    onError: (err: Error) => setError(err.message),
  })

  if (lotQuery.isLoading) {
    return (
      <Card className="border-primary/30 bg-primary/5">
        <CardHeader>
          <CardTitle className="text-base">{tr('Digitalni pasoš / QR kod')}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">{tr('Učitavanje…')}</p>
        </CardContent>
      </Card>
    )
  }

  if (!lot) {
    return (
      <Card className="border-primary/30 bg-primary/5">
        <CardHeader>
          <CardTitle className="text-base">{tr('Digitalni pasoš / QR kod')}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            {tr('Ovde kreirate javni Digitalni pasoš proizvoda i QR kod za ovu berbu.')}
          </p>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={allowIndexing}
              onChange={(e) => setAllowIndexing(e.target.checked)}
            />
            {tr('Dozvoli indeksiranje od strane pretraživača')}
          </label>
          {error ? <p className="text-sm text-danger">{error}</p> : null}
          <Button disabled={createMutation.isPending} onClick={() => createMutation.mutate()}>
            {tr('Kreiraj Digitalni pasoš proizvoda')}
          </Button>
        </CardContent>
      </Card>
    )
  }

  const qrSrc = publicPassportQrUrl(lot.passport_token)
  const statusLabel =
    lot.passport_status === 'finalized'
      ? tr('Finalizovan')
      : lot.passport_status === 'revoked'
        ? tr('Opozvan')
        : 'Objavljen'

  return (
    <Card className="border-primary/30 bg-primary/5 print:border-0 print:shadow-none print:bg-transparent">
      <CardHeader className="print:hidden">
        <CardTitle className="text-base">{tr('Digitalni pasoš / QR kod')}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {lot.passport_status !== 'revoked' ? (
          <div className="print:hidden">
            <PassportFacts
              producer={lot.producer_name}
              location={lot.parcel_location}
              lotNumber={lot.lot_number}
              crop={lot.crop}
              varieties={lot.varieties ?? []}
              harvestDate={lot.harvest_date}
            />
          </div>
        ) : null}

        {lot.passport_status !== 'revoked' ? (
          <div className="flex flex-col items-center gap-3 rounded-xl border border-border bg-muted/30 p-4 print:hidden">
            <img src={qrSrc} alt={`QR kod za lot ${lot.lot_number}`} className="h-44 w-44 bg-white p-2" />
            <p className="text-center text-xs text-muted-foreground break-all">{lot.public_url}</p>
            <div className="flex flex-wrap justify-center gap-2 print:hidden">
              <a href={qrSrc} download={`${lot.lot_number}-qr.png`}>
                <Button variant="outline" size="sm">
                  Preuzmi QR
                </Button>
              </a>
              <Button variant="outline" size="sm" onClick={() => window.print()}>
                {tr('Štampaj etiketu')}
              </Button>
              <Link to={`/passport/${lot.passport_token}`} target="_blank">
                <Button variant="outline" size="sm">
                  {tr("Pregled")}
                </Button>
              </Link>
            </div>
          </div>
        ) : (
          <div className="space-y-3 rounded-xl border border-danger/30 bg-danger/5 p-4">
            <p className="text-sm text-danger">{tr('Ovaj pasoš je opozvan i više nije javno dostupan.')}</p>
            <Button size="sm" disabled={restoreMutation.isPending} onClick={() => restoreMutation.mutate()}>
              {tr('Ponovo aktiviraj pasoš')}
            </Button>
          </div>
        )}

        {lot.passport_status !== 'revoked' ? (
          <div className="hidden print:block">
            <div className="mx-auto max-w-xs space-y-4 border border-black bg-white p-4 text-black">
              <img src={qrSrc} alt="" className="mx-auto h-36 w-36" />
              <PassportFacts
                producer={lot.producer_name}
                location={lot.parcel_location}
                lotNumber={lot.lot_number}
                crop={lot.crop}
                varieties={lot.varieties ?? []}
                harvestDate={lot.harvest_date}
              />
            </div>
          </div>
        ) : null}

        {error ? <p className="text-sm text-danger print:hidden">{error}</p> : null}

        <p className="text-xs text-muted-foreground print:hidden">Status: {statusLabel}</p>

        <div className="flex flex-wrap gap-2 print:hidden">
          {lot.passport_status === 'published' ? (
            <Button
              size="sm"
              disabled={finalizeMutation.isPending}
              onClick={() => {
                if (!window.confirm(tr('Finalizacija čuva nepromenljivi snimak javnih podataka. Nastaviti?'))) return
                finalizeMutation.mutate()
              }}
            >
              {tr('Finalizuj pasoš')}
            </Button>
          ) : null}
          {lot.passport_status !== 'revoked' ? (
            <Button
              variant="outline"
              size="sm"
              disabled={revokeMutation.isPending}
              onClick={() => {
                if (!window.confirm(tr('Opozvati javni pasoš? QR više neće raditi.'))) return
                revokeMutation.mutate()
              }}
            >
              Opozovi
            </Button>
          ) : (
            <Button size="sm" disabled={restoreMutation.isPending} onClick={() => restoreMutation.mutate()}>
              Ponovo aktiviraj
            </Button>
          )}
        </div>

        <div className="print:hidden">
          <Label className="text-xs text-muted-foreground">
            {tr('Javni URL koristi nasumični token — interni ID-jevi se ne izlažu.')}
          </Label>
        </div>
      </CardContent>
    </Card>
  )
}
