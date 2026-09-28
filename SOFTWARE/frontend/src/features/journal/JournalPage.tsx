import { useMemo, useState, type ReactNode } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'

import { JournalCalendar } from '@/features/journal/JournalCalendar'
import { listActivities, listActivityTypes } from '@/features/journal/api'
import { daysInMonth, journalCalendarSpan, monthRange, todayKey } from '@/features/journal/calendar'
import { activityCalendarKind, activityStatusLabel, activityStatuses } from '@/features/journal/labels'
import { listParcels, listParcelRows, listParcelTrees } from '@/features/orchard/api'
import type { ActivityFilters, ActivityScope, ActivityStatus } from '@/shared/api/types'
import { activityTarget, formatDate, formatMoney, formatWorkQuantities, rowLabel, scopeLabel } from '@/shared/lib/format'
import { cn } from '@/shared/lib/utils'
import { Button } from '@/shared/ui/button'
import { Card, CardContent } from '@/shared/ui/card'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { Select } from '@/shared/ui/select'

export function JournalPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [view, setView] = useState<'calendar' | 'list'>(() => (searchParams.get('view') === 'list' ? 'list' : 'calendar'))
  const [selectedDay, setSelectedDay] = useState<string | null>(() => todayKey())
  const [filters, setFilters] = useState<ActivityFilters>(() => ({
    parcel_id: searchParams.get('parcelId') || searchParams.get('parcel_id') || '',
    date_from: searchParams.get('date_from') || '',
    date_to: searchParams.get('date_to') || '',
    activity_type_id: searchParams.get('activity_type_id') || '',
    scope_type: (searchParams.get('scope_type') as ActivityScope | '') || '',
    row_id: searchParams.get('row_id') || '',
    tree_id: searchParams.get('tree_id') || '',
    status: (searchParams.get('status') as ActivityStatus | '') || '',
  }))
  const listReturnTo = useMemo(() => journalListPath(filters), [filters])
  const createActivityTo =
    view === 'list'
      ? `/activities/new?returnTo=${encodeURIComponent(listReturnTo)}`
      : '/activities/new'
  const typesQuery = useQuery({ queryKey: ['activity-types'], queryFn: listActivityTypes })
  const parcelsQuery = useQuery({ queryKey: ['parcels'], queryFn: listParcels })
  const calendarRange = useMemo(() => {
    const span = journalCalendarSpan()
    const months = monthRange(span.fromYear, span.fromMonth, span.toYear, span.toMonth)
    const first = months[0]
    const last = months[months.length - 1]
    return {
      date_from: `${first.year}-${String(first.month).padStart(2, '0')}-01`,
      date_to: `${last.year}-${String(last.month).padStart(2, '0')}-${String(daysInMonth(last.year, last.month)).padStart(2, '0')}`,
    }
  }, [])
  const rowsQuery = useQuery({
    queryKey: ['parcel-rows', filters.parcel_id],
    queryFn: () => listParcelRows(filters.parcel_id!),
    enabled: Boolean(filters.parcel_id) && view === 'list',
  })
  const treesQuery = useQuery({
    queryKey: ['parcel-trees', filters.parcel_id, filters.row_id],
    queryFn: () => listParcelTrees(filters.parcel_id!, filters.row_id),
    enabled: Boolean(filters.parcel_id && filters.row_id) && view === 'list',
  })
  const calendarQuery = useQuery({
    queryKey: ['activities', 'calendar', calendarRange, filters.parcel_id, filters.activity_type_id, filters.scope_type],
    queryFn: () =>
      listActivities({
        date_from: calendarRange.date_from,
        date_to: calendarRange.date_to,
        parcel_id: filters.parcel_id,
        activity_type_id: filters.activity_type_id,
        scope_type: filters.scope_type,
      }),
    enabled: view === 'calendar',
  })
  const listQuery = useQuery({
    queryKey: ['activities', 'list', filters],
    queryFn: () => listActivities(filters),
    enabled: view === 'list',
  })
  const listActivitiesData = listQuery.data ?? []
  const grouped = useMemo(() => {
    const map = new Map<string, typeof listActivitiesData>()
    for (const activity of listActivitiesData) {
      const key = activity.performed_on
      map.set(key, [...(map.get(key) ?? []), activity])
    }
    return [...map.entries()]
  }, [listActivitiesData])

  function setJournalView(next: 'calendar' | 'list') {
    setView(next)
    const params = new URLSearchParams(searchParams)
    if (next === 'list') params.set('view', 'list')
    else params.delete('view')
    setSearchParams(params, { replace: true })
  }

  function update<K extends keyof ActivityFilters>(key: K, value: ActivityFilters[K]) {
    setFilters((current) => {
      const next = { ...current, [key]: value }
      if (key === 'parcel_id') {
        next.row_id = ''
        next.tree_id = ''
      }
      if (key === 'row_id') next.tree_id = ''
      if (key === 'scope_type' && value === 'parcel') {
        next.row_id = ''
        next.tree_id = ''
      }
      return next
    })
  }

  return (
    <div className="w-full space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end sm:justify-between sm:gap-4">
        <div>
          <p className="kicker">Dnevnik voćnjaka</p>
          <h1 className="mt-1 text-xl font-semibold sm:text-2xl">Aktivnosti</h1>
        </div>
        <div className="flex w-full min-w-0 flex-nowrap items-center gap-1.5 sm:w-auto sm:gap-2">
          <div className="inline-flex shrink-0 rounded-md border border-border p-0.5">
            <ViewButton active={view === 'calendar'} onClick={() => setJournalView('calendar')}>
              Kalendar
            </ViewButton>
            <ViewButton active={view === 'list'} onClick={() => setJournalView('list')}>
              Lista
            </ViewButton>
          </div>
          <Link to="/journal/schedule" className="shrink-0">
            <Button variant="outline" size="sm" className="h-9 px-2.5 text-xs sm:h-10 sm:px-3 sm:text-sm">
              Planiranje
            </Button>
          </Link>
          <Link to={createActivityTo} className="min-w-0 shrink">
            <Button size="sm" className="h-9 px-2.5 text-xs sm:h-10 sm:px-3 sm:text-sm">
              + Dodaj aktivnost
            </Button>
          </Link>
        </div>
      </div>

      <Card>
        <CardContent className={cn('grid gap-3 py-4', view === 'calendar' ? 'md:grid-cols-3' : 'md:grid-cols-4')}>
          {view === 'list' ? (
            <>
              <Filter label="Od">
                <Input type="date" value={filters.date_from ?? ''} onChange={(event) => update('date_from', event.target.value)} />
              </Filter>
              <Filter label="Do">
                <Input type="date" value={filters.date_to ?? ''} onChange={(event) => update('date_to', event.target.value)} />
              </Filter>
            </>
          ) : null}
          <Filter label="Tip aktivnosti">
            <Select
              value={filters.activity_type_id ?? ''}
              onChange={(event) => update('activity_type_id', event.target.value)}
            >
              <option value="">Svi tipovi</option>
              {(typesQuery.data ?? []).map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </Select>
          </Filter>
          <Filter label="Obuhvat">
            <Select
              value={filters.scope_type ?? ''}
              onChange={(event) => update('scope_type', event.target.value as ActivityScope | '')}
            >
              <option value="">Svi obuhvati</option>
              <option value="parcel">Parcela</option>
              <option value="row">Red</option>
              <option value="tree">Stablo</option>
            </Select>
          </Filter>
          <Filter label="Parcela">
            <Select value={filters.parcel_id ?? ''} onChange={(event) => update('parcel_id', event.target.value)}>
              <option value="">Sve parcele</option>
              {(parcelsQuery.data ?? []).map((parcel) => (
                <option key={parcel.id} value={parcel.id}>
                  {parcel.name}
                </option>
              ))}
            </Select>
          </Filter>
          {view === 'list' ? (
            <>
              <Filter label="Red">
                <Select value={filters.row_id ?? ''} onChange={(event) => update('row_id', event.target.value)} disabled={!filters.parcel_id}>
                  <option value="">Svi redovi</option>
                  {(rowsQuery.data ?? []).map((row) => (
                    <option key={row.id} value={row.id}>
                      {row.name ?? rowLabel(row.row_number)}
                    </option>
                  ))}
                </Select>
              </Filter>
              <Filter label="Stablo">
                <Select value={filters.tree_id ?? ''} onChange={(event) => update('tree_id', event.target.value)} disabled={!filters.row_id}>
                  <option value="">Sva stabla</option>
                  {(treesQuery.data ?? []).map((tree) => (
                    <option key={tree.id} value={tree.id}>
                      {tree.public_id}
                    </option>
                  ))}
                </Select>
              </Filter>
              <Filter label="Status">
                <Select
                  value={filters.status ?? ''}
                  onChange={(event) => update('status', event.target.value as ActivityStatus | '')}
                >
                  <option value="">Svi statusi</option>
                  {activityStatuses.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </Select>
              </Filter>
            </>
          ) : null}
        </CardContent>
      </Card>

      {view === 'calendar' ? (
        calendarQuery.isLoading ? (
          <p className="text-sm text-muted-foreground">Učitavanje kalendara…</p>
        ) : (
          <JournalCalendar
            selectedDay={selectedDay}
            activities={calendarQuery.data ?? []}
            onSelectDay={setSelectedDay}
          />
        )
      ) : listQuery.isLoading ? (
        <p className="text-sm text-muted-foreground">Učitavanje dnevnika…</p>
      ) : grouped.length === 0 ? (
        <p className="text-sm text-muted-foreground">Nema aktivnosti za ove filtere.</p>
      ) : (
        <div className="space-y-6">
          {grouped.map(([day, items]) => (
            <section key={day} className="space-y-2">
              <h2 className="font-mono text-sm text-muted-foreground">{formatDate(day)}</h2>
              {items.map((activity) => {
                const kind = activityCalendarKind(activity.status, activity.performed_on, todayKey())
                return (
                  <Link
                    key={activity.id}
                    to={`/activities/${activity.id}?returnTo=${encodeURIComponent(listReturnTo)}`}
                    className="block"
                  >
                    <Card className="hover:bg-muted/40">
                      <CardContent className="flex items-center justify-between gap-3 py-4">
                        <div className="min-w-0">
                          <p className="font-medium">{activity.activity_type.name}</p>
                          <p className="text-sm text-muted-foreground">
                            {scopeLabel(activity.scope_type)} · {activityTarget(activity)} ·{' '}
                            {kind === 'overdue' ? 'Kasni' : activityStatusLabel(activity.status)}
                          </p>
                          {formatWorkQuantities(activity.line_items) ? (
                            <p className="text-[11px] leading-4 text-muted-foreground">
                              {formatWorkQuantities(activity.line_items)}
                            </p>
                          ) : null}
                        </div>
                        <p className="shrink-0 font-mono text-sm">{formatMoney(activity.total_cost, activity.currency)}</p>
                      </CardContent>
                    </Card>
                  </Link>
                )
              })}
            </section>
          ))}
        </div>
      )}
    </div>
  )
}

function ViewButton({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'h-8 rounded-md px-2 text-[11px] font-medium sm:h-9 sm:px-2.5 sm:text-xs',
        active ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground',
      )}
    >
      {children}
    </button>
  )
}

function Filter({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      {children}
    </div>
  )
}

function journalListPath(filters: ActivityFilters) {
  const params = new URLSearchParams({ view: 'list' })
  for (const [key, value] of Object.entries(filters)) {
    if (value) params.set(key, String(value))
  }
  return `/journal?${params.toString()}`
}
