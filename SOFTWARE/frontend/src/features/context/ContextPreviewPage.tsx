import { useMutation, useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'

import { previewContext } from '@/features/context/api'
import { listActivities } from '@/features/journal/api'
import { listParcelRows, listParcelTrees, listParcels } from '@/features/orchard/api'
import type { ContextRequestType } from '@/shared/api/types'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { Select } from '@/shared/ui/select'

const REQUEST_TYPES: Array<{ value: ContextRequestType; label: string }> = [
  { value: 'PHOTO_ANALYSIS', label: 'PHOTO_ANALYSIS' },
  { value: 'PROBLEM_ANALYSIS', label: 'PROBLEM_ANALYSIS' },
  { value: 'PARCEL_ANALYSIS', label: 'PARCEL_ANALYSIS' },
  { value: 'SEASON_ANALYSIS', label: 'SEASON_ANALYSIS' },
  { value: 'ACTIVITY_ANALYSIS', label: 'ACTIVITY_ANALYSIS' },
]

export function ContextPreviewPage() {
  const parcelsQuery = useQuery({ queryKey: ['parcels'], queryFn: listParcels })
  const [requestType, setRequestType] = useState<ContextRequestType>('PHOTO_ANALYSIS')
  const [parcelId, setParcelId] = useState('')
  const [rowId, setRowId] = useState('')
  const [treeId, setTreeId] = useState('')
  const [photoId, setPhotoId] = useState('')
  const [activityId, setActivityId] = useState('')
  const [query, setQuery] = useState('')
  const parcels = parcelsQuery.data ?? []
  const rowsQuery = useQuery({
    queryKey: ['parcel-rows', parcelId],
    queryFn: () => listParcelRows(parcelId),
    enabled: Boolean(parcelId),
  })
  const treesQuery = useQuery({
    queryKey: ['parcel-trees', parcelId, rowId],
    queryFn: () => listParcelTrees(parcelId, rowId || undefined),
    enabled: Boolean(parcelId),
  })
  const activitiesQuery = useQuery({
    queryKey: ['context-activities', parcelId],
    queryFn: () => listActivities({ parcel_id: parcelId }),
    enabled: Boolean(parcelId) && requestType === 'ACTIVITY_ANALYSIS',
  })

  const mutation = useMutation({
    mutationFn: previewContext,
  })

  const selected = useMemo(
    () => mutation.data?.debug?.records.filter((item) => item.selected) ?? [],
    [mutation.data],
  )
  const excluded = useMemo(
    () => mutation.data?.debug?.records.filter((item) => !item.selected) ?? [],
    [mutation.data],
  )

  function generate() {
    mutation.mutate({
      request_type: requestType,
      parcel_id: parcelId || undefined,
      row_id: rowId || undefined,
      tree_id: treeId || undefined,
      photo_id: photoId.trim() || undefined,
      activity_id: activityId || undefined,
      query: query.trim() || undefined,
    })
  }

  return (
    <div className="w-full space-y-6">
      <div>
        <p className="kicker">Razvoj</p>
        <h1 className="mt-1 text-xl font-semibold sm:text-2xl">Context Engine pregled</h1>
        <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
          Interni alat. Generiše strukturirani AgroTwinContext bez AI zaključivanja.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Zahtev</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <div className="space-y-2">
            <Label htmlFor="context-type">Tip konteksta</Label>
            <Select
              id="context-type"
              value={requestType}
              onChange={(event) => setRequestType(event.target.value as ContextRequestType)}
            >
              {REQUEST_TYPES.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="context-parcel">Parcela</Label>
            <Select
              id="context-parcel"
              value={parcelId}
              onChange={(event) => {
                setParcelId(event.target.value)
                setRowId('')
                setTreeId('')
                setActivityId('')
              }}
            >
              <option value="">—</option>
              {parcels.map((parcel) => (
                <option key={parcel.id} value={parcel.id}>
                  {parcel.name}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="context-row">Red</Label>
            <Select
              id="context-row"
              value={rowId}
              disabled={!parcelId}
              onChange={(event) => {
                setRowId(event.target.value)
                setTreeId('')
              }}
            >
              <option value="">—</option>
              {(rowsQuery.data ?? []).map((row) => (
                <option key={row.id} value={row.id}>
                  Red {row.row_number}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="context-tree">Stablo</Label>
            <Select
              id="context-tree"
              value={treeId}
              disabled={!parcelId}
              onChange={(event) => setTreeId(event.target.value)}
            >
              <option value="">—</option>
              {(treesQuery.data ?? []).map((tree) => (
                <option key={tree.id} value={tree.id}>
                  {tree.public_id}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="context-photo">Foto ID</Label>
            <Input
              id="context-photo"
              value={photoId}
              onChange={(event) => setPhotoId(event.target.value)}
              placeholder="opciono UUID"
            />
          </div>
          {requestType === 'ACTIVITY_ANALYSIS' ? (
            <div className="space-y-2">
              <Label htmlFor="context-activity">Aktivnost</Label>
              <Select
                id="context-activity"
                value={activityId}
                disabled={!parcelId}
                onChange={(event) => setActivityId(event.target.value)}
              >
                <option value="">—</option>
                {(activitiesQuery.data ?? []).map((activity) => (
                  <option key={activity.id} value={activity.id}>
                    {activity.title}
                  </option>
                ))}
              </Select>
            </div>
          ) : null}
          <div className="space-y-2 sm:col-span-2">
            <Label htmlFor="context-query">Upit</Label>
            <Input
              id="context-query"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Šta se dešava sa listovima?"
            />
          </div>
          <div className="flex items-end">
            <Button type="button" onClick={generate} disabled={mutation.isPending}>
              Generiši kontekst
            </Button>
          </div>
        </CardContent>
      </Card>

      {mutation.error ? (
        <p className="text-sm text-destructive">{mutation.error.message}</p>
      ) : null}

      {mutation.data ? (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Upozorenja i kvalitet</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <p>
                Trajanje {mutation.data.debug?.duration_ms ?? 0} ms · izvori:{' '}
                {(mutation.data.debug?.providers_used ?? []).join(', ') || '—'}
              </p>
              <ul className="list-disc space-y-1 pl-5">
                {mutation.data.warnings.length === 0 ? <li>Nema upozorenja.</li> : null}
                {mutation.data.warnings.map((warning) => (
                  <li key={`${warning.source}-${warning.type}`}>
                    {warning.source}: {warning.message}
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Izabrani zapisi</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              {selected.length === 0 ? <p className="text-muted-foreground">Nema izabranih zapisa.</p> : null}
              {selected.map((item) => (
                <div key={`${item.kind}-${item.id}`} className="rounded-lg border border-border px-3 py-2">
                  <p className="font-medium">
                    {item.kind} {item.id.slice(0, 8)} · {item.scope ?? '—'} · {item.relevance_score}
                  </p>
                  <p className="text-muted-foreground">
                    {item.date ?? 'bez datuma'} · {item.temporal_relation ?? '—'}
                  </p>
                  <p>{item.reasons.join(' · ')}</p>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Isključeni zapisi</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              {excluded.length === 0 ? <p className="text-muted-foreground">Nema isključenih zapisa u pregledu.</p> : null}
              {excluded.map((item) => (
                <div key={`${item.kind}-${item.id}`} className="rounded-lg border border-border px-3 py-2">
                  <p className="font-medium">
                    {item.kind} {item.id.slice(0, 8)} · {item.scope ?? '—'} · {item.relevance_score}
                  </p>
                  <p>{item.reasons.join(' · ')}</p>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>JSON</CardTitle>
            </CardHeader>
            <CardContent>
              <pre className="max-h-[32rem] overflow-auto rounded-lg bg-muted p-4 text-xs">
                {JSON.stringify(mutation.data, null, 2)}
              </pre>
            </CardContent>
          </Card>
        </>
      ) : null}
    </div>
  )
}
