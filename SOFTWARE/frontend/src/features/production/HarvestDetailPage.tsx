import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { PhotoGallery } from '@/features/health/PhotoGallery'
import { deleteHarvest, getHarvest } from '@/features/production/api'
import { HarvestForm } from '@/features/production/HarvestForm'
import { qualityLabel } from '@/features/production/labels'
import { formatDate, formatKg, scopeLabel } from '@/shared/lib/format'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'

export function HarvestDetailPage() {
  const { parcelId, harvestId } = useParams()
  const [params] = useSearchParams()
  const year = Number(params.get('year') || '') || undefined
  const [editing, setEditing] = useState(false)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const harvestQuery = useQuery({
    queryKey: ['harvest', parcelId, harvestId],
    queryFn: () => getHarvest(parcelId!, harvestId!),
    enabled: Boolean(parcelId && harvestId),
  })
  const harvest = harvestQuery.data
  const deleteMutation = useMutation({
    mutationFn: () => deleteHarvest(parcelId!, harvestId!),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['parcel-production', parcelId] })
      await queryClient.invalidateQueries({ queryKey: ['parcel-report', parcelId] })
      void navigate(`/orchard/${parcelId}/production${year ? `?year=${year}` : ''}`)
    },
  })

  if (!parcelId || !harvestId) return null
  if (harvestQuery.isLoading) return <p className="text-sm text-muted-foreground">Učitavanje berbe…</p>
  if (!harvest) return <p className="text-sm text-danger">Berba nije pronađena.</p>

  const harvestYear = year || Number(harvest.harvested_on.slice(0, 4))
  const backHref = `/orchard/${parcelId}/production?year=${harvestYear}`

  return (
    <div className="w-full space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="kicker">Proizvodnja</p>
          <h1 className="mt-1 text-xl font-semibold sm:text-2xl">{formatDate(harvest.harvested_on)}</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {scopeLabel(harvest.scope_type)} · {harvest.location_label} · {formatKg(harvest.net_kg ?? harvest.net_quantity)} neto
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => setEditing((value) => !value)}>
            {editing ? 'Pregled' : 'Izmeni'}
          </Button>
          <Button
            variant="outline"
            disabled={deleteMutation.isPending}
            onClick={() => {
              if (!window.confirm('Obrisati ovu berbu? Prinos parcele biće ponovo izračunat.')) return
              deleteMutation.mutate()
            }}
          >
            Obriši
          </Button>
        </div>
      </div>

      {editing ? (
        <div className="rounded-xl border border-border bg-card p-4 sm:p-6">
          <HarvestForm parcelId={parcelId} harvest={harvest} year={harvestYear} />
        </div>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Detalj berbe</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              <Item label="Datum" value={formatDate(harvest.harvested_on)} />
              <Item label="Obuhvat" value={scopeLabel(harvest.scope_type)} />
              <Item label="Lokacija" value={harvest.location_label} />
              <Item label="Bruto" value={formatKg(harvest.gross_kg ?? harvest.gross_quantity)} />
              <Item label="Gubitak" value={formatKg(harvest.loss_kg ?? harvest.loss_quantity)} />
              <Item label="Neto" value={formatKg(harvest.net_kg ?? harvest.net_quantity)} />
              <Item label="Jedinica" value={harvest.unit} />
              <Item label="Vlažnost" value={percent(harvest.moisture_percent)} />
              <Item label="Kvalitet" value={qualityLabel(harvest.quality_category)} />
              <Item label="Oštećeni plodovi" value={percent(harvest.damaged_percent)} />
              <Item label="Prazni plodovi" value={percent(harvest.empty_nuts_percent)} />
              <Item label="Strane materije" value={percent(harvest.foreign_material_percent)} />
              <Item label="Krupnoća" value={harvest.size_or_caliber || '—'} />
            </dl>
            {harvest.notes ? <p>{harvest.notes}</p> : null}
            <p className="text-xs text-muted-foreground">
              Unos: {harvest.created_by_name || '—'} · {formatDateTime(harvest.created_at)}
              {harvest.updated_at !== harvest.created_at ? ` · izmenjeno ${formatDateTime(harvest.updated_at)}` : ''}
            </p>
            {harvest.photos.length > 0 ? <PhotoGallery photos={harvest.photos} /> : null}
          </CardContent>
        </Card>
      )}

      {deleteMutation.error ? (
        <p className="text-sm text-danger">
          {deleteMutation.error instanceof Error ? deleteMutation.error.message : 'Brisanje nije uspelo'}
        </p>
      ) : null}

      <Link to={backHref} className="text-sm text-muted-foreground hover:text-foreground">
        Nazad na proizvodnju
      </Link>
    </div>
  )
}

function Item({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-1 font-medium">{value}</dd>
    </div>
  )
}

function percent(value: string | null) {
  if (value == null || value === '') return '—'
  return `${value} %`
}

function formatDateTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('sr-Latn-RS', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}
