import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'

import { listDiseaseCases } from '@/features/health/cases'
import { categoryLabel, diseaseCategories, diseaseStatuses, severityLabel, statusLabel } from '@/features/health/labels'
import { listParcels } from '@/features/orchard/api'
import type { DiseaseCategory, DiseaseStatus } from '@/shared/api/types'
import { formatDate } from '@/shared/lib/format'
import { Button } from '@/shared/ui/button'
import { Card, CardContent } from '@/shared/ui/card'
import { Label } from '@/shared/ui/label'
import { Select } from '@/shared/ui/select'

export function HealthIndexPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [parcelId, setParcelId] = useState(() => searchParams.get('parcelId') || searchParams.get('parcel') || '')
  const [status, setStatus] = useState<DiseaseStatus | ''>(
    () => (searchParams.get('status') as DiseaseStatus | '') || '',
  )
  const [category, setCategory] = useState<DiseaseCategory | ''>(
    () => (searchParams.get('category') as DiseaseCategory | '') || '',
  )
  const listReturnTo = useMemo(() => healthListPath(parcelId, status, category), [parcelId, status, category])
  const parcelsQuery = useQuery({ queryKey: ['parcels'], queryFn: listParcels })
  const casesQuery = useQuery({
    queryKey: ['disease-cases', parcelId, status, category],
    queryFn: () => listDiseaseCases({ parcel_id: parcelId, status, category }),
  })
  const cases = casesQuery.data ?? []

  useEffect(() => {
    const next = healthSearchParams(parcelId, status, category)
    if (next.toString() === searchParams.toString()) return
    setSearchParams(next, { replace: true })
  }, [parcelId, status, category, searchParams, setSearchParams])

  return (
    <div className="w-full space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="kicker">Zdravlje stabala</p>
          <h1 className="mt-1 text-xl font-semibold sm:text-2xl">Opažanja i sumnje na probleme</h1>
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
            Ovo su terenska opažanja, a ne potvrđene agronomske dijagnoze.
          </p>
        </div>
        <Link to={`/health/new?returnTo=${encodeURIComponent(listReturnTo)}`}>
          <Button>+ Prijavi problem</Button>
        </Link>
      </div>

      <Card>
        <CardContent className="grid gap-3 py-4 md:grid-cols-3">
          <div className="space-y-1.5">
            <Label>Parcela</Label>
            <Select value={parcelId} onChange={(event) => setParcelId(event.target.value)}>
              <option value="">Sve parcele</option>
              {(parcelsQuery.data ?? []).map((parcel) => (
                <option key={parcel.id} value={parcel.id}>
                  {parcel.name}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>Status</Label>
            <Select value={status} onChange={(event) => setStatus(event.target.value as DiseaseStatus | '')}>
              <option value="">Svi statusi</option>
              {diseaseStatuses.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>Kategorija</Label>
            <Select value={category} onChange={(event) => setCategory(event.target.value as DiseaseCategory | '')}>
              <option value="">Sve kategorije</option>
              {diseaseCategories.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </Select>
          </div>
        </CardContent>
      </Card>

      {casesQuery.isLoading ? (
        <p className="text-sm text-muted-foreground">Učitavanje opažanja…</p>
      ) : cases.length === 0 ? (
        <p className="text-sm text-muted-foreground">Nema opažanja za ove filtere.</p>
      ) : (
        <div className="space-y-3">
          {cases.map((item) => (
            <Link
              key={item.id}
              to={`/health/${item.id}?returnTo=${encodeURIComponent(listReturnTo)}`}
              className="block"
            >
              <Card className="hover:bg-muted/40">
                <CardContent className="flex items-start justify-between gap-4 py-4">
                  <div>
                    <p className="font-medium">{item.title}</p>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {formatDate(item.detected_on)} · {categoryLabel(item.category)} · {item.tree_public_id ?? item.parcel_name}
                    </p>
                  </div>
                  <div className="text-right text-xs uppercase tracking-wide text-muted-foreground">
                    <p>{statusLabel(item.status)}</p>
                    <p className="mt-1">{severityLabel(item.severity)}</p>
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}

function healthSearchParams(parcelId: string, status: string, category: string) {
  const params = new URLSearchParams()
  if (parcelId) params.set('parcelId', parcelId)
  if (status) params.set('status', status)
  if (category) params.set('category', category)
  return params
}

function healthListPath(parcelId: string, status: string, category: string) {
  const params = healthSearchParams(parcelId, status, category)
  const query = params.toString()
  return query ? `/health?${query}` : '/health'
}
