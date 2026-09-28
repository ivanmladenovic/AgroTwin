import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState, type FormEvent } from 'react'

import { listActivityTypes } from '@/features/journal/api'
import {
  createSchedule,
  createSeason,
  deleteSchedule,
  deleteSeason,
  listSchedules,
  listSeasons,
} from '@/features/journal/scheduleApi'
import { listParcels } from '@/features/orchard/api'
import { formatDate } from '@/shared/lib/format'
import { BackButton } from '@/shared/ui/back-button'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { Select } from '@/shared/ui/select'
import { Textarea } from '@/shared/ui/textarea'

const WEEKDAYS: Array<{ value: number; label: string; short: string }> = [
  { value: 0, label: 'Ponedeljak', short: 'Pon' },
  { value: 1, label: 'Utorak', short: 'Uto' },
  { value: 2, label: 'Sreda', short: 'Sre' },
  { value: 3, label: 'Četvrtak', short: 'Čet' },
  { value: 4, label: 'Petak', short: 'Pet' },
  { value: 5, label: 'Subota', short: 'Sub' },
  { value: 6, label: 'Nedelja', short: 'Ned' },
]

type WindowMode = 'season' | 'year' | 'custom'

export function SchedulePage() {
  const queryClient = useQueryClient()
  const [parcelId, setParcelId] = useState('')
  const seasonsQuery = useQuery({ queryKey: ['seasons', parcelId], queryFn: () => listSeasons(parcelId || undefined) })
  const schedulesQuery = useQuery({
    queryKey: ['schedules', parcelId],
    queryFn: () => listSchedules(parcelId || undefined),
  })
  const parcelsQuery = useQuery({ queryKey: ['parcels'], queryFn: listParcels })
  const typesQuery = useQuery({ queryKey: ['activity-types'], queryFn: listActivityTypes })

  const removeSeason = useMutation({
    mutationFn: deleteSeason,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['seasons'] })
    },
  })
  const removeSchedule = useMutation({
    mutationFn: deleteSchedule,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['schedules'] })
      await queryClient.invalidateQueries({ queryKey: ['activities'] })
    },
  })

  const seasons = seasonsQuery.data ?? []
  const schedules = schedulesQuery.data ?? []

  return (
    <div className="w-full space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="kicker">Dnevnik</p>
          <h1 className="mt-1 text-xl font-semibold sm:text-2xl">Planiranje zadataka</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Definišite sezone i ponavljajuće zadatke. Sistem ih upisuje u kalendar kao planirane aktivnosti.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <BackButton fallback="/journal">Nazad na dnevnik</BackButton>
        </div>
      </div>

      <div className="max-w-xs">
        <Label htmlFor="plan-parcel">Parcela</Label>
        <Select id="plan-parcel" value={parcelId} onChange={(event) => setParcelId(event.target.value)}>
          <option value="">Sve parcele</option>
          {(parcelsQuery.data ?? []).map((parcel) => (
            <option key={parcel.id} value={parcel.id}>
              {parcel.name}
            </option>
          ))}
        </Select>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Sezone</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <SeasonForm
              parcels={parcelsQuery.data ?? []}
              defaultParcelId={parcelId}
              onDone={async () => {
                await queryClient.invalidateQueries({ queryKey: ['seasons'] })
              }}
            />
            {seasonsQuery.isLoading ? (
              <p className="text-sm text-muted-foreground">Učitavanje sezona…</p>
            ) : seasons.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Nema sezona. Npr. „Navodnjavanje maj–septembar“ ili „Berba 2026“.
              </p>
            ) : (
              <div className="space-y-2">
                {seasons.map((season) => (
                  <div key={season.id} className="flex items-start justify-between gap-3 rounded-lg border border-border/60 px-3 py-2 text-sm">
                    <div className="min-w-0">
                      <p className="font-medium">{season.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {formatDate(season.starts_on)} – {formatDate(season.ends_on)}
                        {season.parcel_name ? ` · ${season.parcel_name}` : ''}
                      </p>
                    </div>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="shrink-0 text-destructive"
                      disabled={removeSeason.isPending}
                      onClick={() => {
                        if (window.confirm('Obrisati sezonu? Rasporedi ostaju, ali gube vezu sa sezonom.')) {
                          removeSeason.mutate(season.id)
                        }
                      }}
                    >
                      Obriši
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Ponavljajući zadaci</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <ScheduleForm
              parcels={parcelsQuery.data ?? []}
              types={typesQuery.data ?? []}
              seasons={seasons}
              defaultParcelId={parcelId}
              onDone={async () => {
                await queryClient.invalidateQueries({ queryKey: ['schedules'] })
                await queryClient.invalidateQueries({ queryKey: ['activities'] })
              }}
            />
            {schedulesQuery.isLoading ? (
              <p className="text-sm text-muted-foreground">Učitavanje rasporeda…</p>
            ) : schedules.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Nema rasporeda. Npr. navodnjavanje pon/sre/pet u sezoni.
              </p>
            ) : (
              <div className="space-y-2">
                {schedules.map((item) => (
                  <div key={item.id} className="flex items-start justify-between gap-3 rounded-lg border border-border/60 px-3 py-2 text-sm">
                    <div className="min-w-0">
                      <p className="font-medium">{item.title}</p>
                      <p className="text-xs text-muted-foreground">
                        {item.activity_type.name} · {formatWeekdays(item.weekdays)}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {formatDate(item.starts_on)} – {formatDate(item.ends_on)}
                        {item.season_name ? ` · ${item.season_name}` : ''}
                        {item.parcel_name ? ` · ${item.parcel_name}` : ''}
                      </p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {item.planned_count} planiranih dana u kalendaru
                        {!item.is_active ? ' · pauzirano' : ''}
                      </p>
                    </div>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="shrink-0 text-destructive"
                      disabled={removeSchedule.isPending}
                      onClick={() => {
                        if (window.confirm('Obrisati raspored i njegove planirane (neurađene) stavke?')) {
                          removeSchedule.mutate(item.id)
                        }
                      }}
                    >
                      Obriši
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function SeasonForm({
  parcels,
  defaultParcelId,
  onDone,
}: {
  parcels: Array<{ id: string; name: string }>
  defaultParcelId: string
  onDone: () => void | Promise<void>
}) {
  const year = new Date().getFullYear()
  const [name, setName] = useState('')
  const [startsOn, setStartsOn] = useState(`${year}-05-01`)
  const [endsOn, setEndsOn] = useState(`${year}-09-30`)
  const [parcelId, setParcelId] = useState(defaultParcelId)
  const [notes, setNotes] = useState('')
  const create = useMutation({
    mutationFn: createSeason,
    onSuccess: async () => {
      setName('')
      setNotes('')
      await onDone()
    },
  })

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    if (!name.trim()) return
    create.mutate({
      name: name.trim(),
      starts_on: startsOn,
      ends_on: endsOn,
      parcel_id: parcelId || null,
      notes: notes.trim() || null,
    })
  }

  return (
    <form onSubmit={onSubmit} className="space-y-3 rounded-lg border border-border/60 p-3">
      <div className="space-y-1.5">
        <Label htmlFor="season-name">Naziv sezone</Label>
        <Input
          id="season-name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="npr. Navodnjavanje 2026"
          required
        />
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="season-from">Od</Label>
          <Input id="season-from" type="date" value={startsOn} onChange={(event) => setStartsOn(event.target.value)} required />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="season-to">Do</Label>
          <Input id="season-to" type="date" value={endsOn} onChange={(event) => setEndsOn(event.target.value)} required />
        </div>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="season-parcel">Parcela (opciono)</Label>
        <Select id="season-parcel" value={parcelId} onChange={(event) => setParcelId(event.target.value)}>
          <option value="">Cela plantaža</option>
          {parcels.map((parcel) => (
            <option key={parcel.id} value={parcel.id}>
              {parcel.name}
            </option>
          ))}
        </Select>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="season-notes">Napomena</Label>
        <Textarea id="season-notes" rows={2} value={notes} onChange={(event) => setNotes(event.target.value)} />
      </div>
      {create.isError ? (
        <p className="text-sm text-destructive">{create.error instanceof Error ? create.error.message : 'Unos nije uspeo.'}</p>
      ) : null}
      <Button type="submit" disabled={create.isPending}>
        {create.isPending ? 'Čuvanje…' : 'Sačuvaj sezonu'}
      </Button>
    </form>
  )
}

function ScheduleForm({
  parcels,
  types,
  seasons,
  defaultParcelId,
  onDone,
}: {
  parcels: Array<{ id: string; name: string }>
  types: Array<{ id: string; name: string }>
  seasons: Array<{ id: string; name: string; starts_on: string; ends_on: string }>
  defaultParcelId: string
  onDone: () => void | Promise<void>
}) {
  const year = new Date().getFullYear()
  const [title, setTitle] = useState('')
  const [activityTypeId, setActivityTypeId] = useState('')
  const [weekdays, setWeekdays] = useState<number[]>([0, 2, 4])
  const [mode, setMode] = useState<WindowMode>('season')
  const [seasonId, setSeasonId] = useState('')
  const [startsOn, setStartsOn] = useState(`${year}-01-01`)
  const [endsOn, setEndsOn] = useState(`${year}-12-31`)
  const [yearValue, setYearValue] = useState(String(year))
  const [parcelId, setParcelId] = useState(defaultParcelId || parcels[0]?.id || '')
  const [notes, setNotes] = useState('')

  const typeOptions = useMemo(() => types, [types])

  const create = useMutation({
    mutationFn: createSchedule,
    onSuccess: async () => {
      setTitle('')
      setNotes('')
      await onDone()
    },
  })

  function toggleDay(day: number) {
    setWeekdays((current) => (current.includes(day) ? current.filter((item) => item !== day) : [...current, day].sort()))
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    if (!title.trim() || !activityTypeId || weekdays.length === 0) return
    create.mutate({
      title: title.trim(),
      activity_type_id: activityTypeId,
      weekdays,
      parcel_id: parcelId || null,
      notes: notes.trim() || null,
      season_id: mode === 'season' ? seasonId || null : null,
      whole_year: mode === 'year',
      year: mode === 'year' ? Number(yearValue) : undefined,
      starts_on: mode === 'custom' ? startsOn : null,
      ends_on: mode === 'custom' ? endsOn : null,
    })
  }

  return (
    <form onSubmit={onSubmit} className="space-y-3 rounded-lg border border-border/60 p-3">
      <div className="space-y-1.5">
        <Label htmlFor="schedule-title">Naziv zadatka</Label>
        <Input
          id="schedule-title"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="npr. Navodnjavanje"
          required
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="schedule-type">Tip aktivnosti</Label>
        <Select id="schedule-type" value={activityTypeId} onChange={(event) => setActivityTypeId(event.target.value)} required>
          <option value="">Izaberite tip</option>
          {typeOptions.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
            </option>
          ))}
        </Select>
      </div>
      <div className="space-y-1.5">
        <Label>Dani u nedelji</Label>
        <div className="flex flex-wrap gap-2">
          {WEEKDAYS.map((day) => {
            const active = weekdays.includes(day.value)
            return (
              <button
                key={day.value}
                type="button"
                onClick={() => toggleDay(day.value)}
                className={
                  active
                    ? 'rounded-md bg-primary px-2.5 py-1.5 text-xs font-medium text-primary-foreground'
                    : 'rounded-md border border-border px-2.5 py-1.5 text-xs text-muted-foreground hover:bg-muted'
                }
              >
                {day.short}
              </button>
            )
          })}
        </div>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="schedule-window">Period</Label>
        <Select
          id="schedule-window"
          value={mode}
          onChange={(event) => setMode(event.target.value as WindowMode)}
        >
          <option value="season">Sezona</option>
          <option value="year">Cela godina</option>
          <option value="custom">Od – do</option>
        </Select>
      </div>
      {mode === 'season' ? (
        <div className="space-y-1.5">
          <Label htmlFor="schedule-season">Sezona</Label>
          <Select id="schedule-season" value={seasonId} onChange={(event) => setSeasonId(event.target.value)} required>
            <option value="">Izaberite sezonu</option>
            {seasons.map((season) => (
              <option key={season.id} value={season.id}>
                {season.name} ({formatDate(season.starts_on)} – {formatDate(season.ends_on)})
              </option>
            ))}
          </Select>
        </div>
      ) : null}
      {mode === 'year' ? (
        <div className="space-y-1.5">
          <Label htmlFor="schedule-year">Godina</Label>
          <Input
            id="schedule-year"
            type="number"
            min={1990}
            max={2100}
            value={yearValue}
            onChange={(event) => setYearValue(event.target.value)}
            required
          />
        </div>
      ) : null}
      {mode === 'custom' ? (
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="schedule-from">Od</Label>
            <Input id="schedule-from" type="date" value={startsOn} onChange={(event) => setStartsOn(event.target.value)} required />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="schedule-to">Do</Label>
            <Input id="schedule-to" type="date" value={endsOn} onChange={(event) => setEndsOn(event.target.value)} required />
          </div>
        </div>
      ) : null}
      <div className="space-y-1.5">
        <Label htmlFor="schedule-parcel">Parcela</Label>
        <Select id="schedule-parcel" value={parcelId} onChange={(event) => setParcelId(event.target.value)} required>
          <option value="">Izaberite parcelu</option>
          {parcels.map((parcel) => (
            <option key={parcel.id} value={parcel.id}>
              {parcel.name}
            </option>
          ))}
        </Select>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="schedule-notes">Napomena</Label>
        <Textarea id="schedule-notes" rows={2} value={notes} onChange={(event) => setNotes(event.target.value)} />
      </div>
      {create.isError ? (
        <p className="text-sm text-destructive">{create.error instanceof Error ? create.error.message : 'Unos nije uspeo.'}</p>
      ) : null}
      <Button type="submit" disabled={create.isPending || weekdays.length === 0}>
        {create.isPending ? 'Čuvanje…' : 'Zakaži u kalendar'}
      </Button>
    </form>
  )
}

function formatWeekdays(days: number[]) {
  return days
    .slice()
    .sort((a, b) => a - b)
    .map((day) => WEEKDAYS.find((item) => item.value === day)?.short ?? String(day))
    .join(', ')
}
