import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'

import { listParcels } from '@/features/orchard/api'
import {
  createWorkTask,
  createWorker,
  deleteWorkTask,
  getWorkforceDashboard,
  listWorkTaskTypes,
  listWorkTasks,
  listWorkers,
  updateWorkTask,
  updateWorker,
} from '@/features/workforce/api'
import type { WorkTask, WorkTaskStatus, Worker } from '@/shared/api/types'
import { formatDate, formatMoney, formatNumber } from '@/shared/lib/format'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { Select } from '@/shared/ui/select'
import { Textarea } from '@/shared/ui/textarea'

import { tr } from '@/shared/i18n/i18n'
function todayKey() {
  return new Date().toISOString().slice(0, 10)
}

function workerLabel(worker: Worker) {
  return `${worker.first_name} ${worker.last_name}`.trim()
}

function statusLabel(status: WorkTaskStatus) {
  if (status === 'planned') return tr('Planirano')
  if (status === 'cancelled') return tr('Otkazano')
  return tr('Završeno')
}

export function WorkforcePage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const queryClient = useQueryClient()

  const [parcelId, setParcelId] = useState(() => searchParams.get('parcelId') || '')
  const [workerId, setWorkerId] = useState(() => searchParams.get('workerId') || '')
  const [taskTypeId, setTaskTypeId] = useState(() => searchParams.get('taskTypeId') || '')
  const [dateFrom, setDateFrom] = useState(() => searchParams.get('dateFrom') || '')
  const [dateTo, setDateTo] = useState(() => searchParams.get('dateTo') || '')

  const [taskFormOpen, setTaskFormOpen] = useState(false)
  const [workerFormOpen, setWorkerFormOpen] = useState(false)
  const [editingTask, setEditingTask] = useState<WorkTask | null>(null)
  const [formError, setFormError] = useState<string | null>(null)

  const filters = useMemo(
    () => ({
      parcel_id: parcelId || undefined,
      worker_id: workerId || undefined,
      task_type_id: taskTypeId || undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
    }),
    [parcelId, workerId, taskTypeId, dateFrom, dateTo],
  )

  useEffect(() => {
    const next = new URLSearchParams()
    if (parcelId) next.set('parcelId', parcelId)
    if (workerId) next.set('workerId', workerId)
    if (taskTypeId) next.set('taskTypeId', taskTypeId)
    if (dateFrom) next.set('dateFrom', dateFrom)
    if (dateTo) next.set('dateTo', dateTo)
    setSearchParams(next, { replace: true })
  }, [parcelId, workerId, taskTypeId, dateFrom, dateTo, setSearchParams])

  const parcelsQuery = useQuery({ queryKey: ['parcels'], queryFn: listParcels })
  const workersQuery = useQuery({ queryKey: ['workers'], queryFn: () => listWorkers(false) })
  const typesQuery = useQuery({ queryKey: ['work-task-types'], queryFn: listWorkTaskTypes })
  const dashboardQuery = useQuery({
    queryKey: ['workforce-dashboard', filters],
    queryFn: () => getWorkforceDashboard(filters),
  })
  const tasksQuery = useQuery({
    queryKey: ['work-tasks', filters],
    queryFn: () => listWorkTasks(filters),
  })

  const invalidate = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['workforce-dashboard'] }),
      queryClient.invalidateQueries({ queryKey: ['work-tasks'] }),
      queryClient.invalidateQueries({ queryKey: ['workers'] }),
      queryClient.invalidateQueries({ queryKey: ['parcel-labor'] }),
      queryClient.invalidateQueries({ queryKey: ['costs'] }),
      queryClient.invalidateQueries({ queryKey: ['cost-summary'] }),
    ])
  }

  const createWorkerMutation = useMutation({
    mutationFn: createWorker,
    onSuccess: async () => {
      setWorkerFormOpen(false)
      setFormError(null)
      await invalidate()
    },
    onError: (error: Error) => setFormError(error.message),
  })

  const updateWorkerMutation = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) => updateWorker(id, { active }),
    onSuccess: async () => {
      await invalidate()
    },
  })

  const saveTaskMutation = useMutation({
    mutationFn: async (payload: {
      worker_id: string
      parcel_id: string
      task_type_id: string
      description: string
      worked_on: string
      hours: string
      hourly_rate: string
      status: WorkTaskStatus
    }) => {
      const body = {
        worker_id: payload.worker_id,
        parcel_id: payload.parcel_id,
        task_type_id: payload.task_type_id,
        description: payload.description || null,
        worked_on: payload.worked_on,
        hours: payload.hours,
        hourly_rate: payload.hourly_rate || null,
        status: payload.status,
      }
      if (editingTask) {
        return updateWorkTask(editingTask.id, body)
      }
      return createWorkTask(body)
    },
    onSuccess: async () => {
      setTaskFormOpen(false)
      setEditingTask(null)
      setFormError(null)
      await invalidate()
    },
    onError: (error: Error) => setFormError(error.message),
  })

  const deleteTaskMutation = useMutation({
    mutationFn: deleteWorkTask,
    onSuccess: async () => {
      await invalidate()
    },
  })

  const dashboard = dashboardQuery.data
  const workers = workersQuery.data ?? []
  const activeWorkers = workers.filter((w) => w.active)
  const types = typesQuery.data ?? []
  const parcels = parcelsQuery.data ?? []
  const tasks = tasksQuery.data ?? []

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{tr("Radna snaga")}</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {tr('Evidentirajte radnike, zadatke i trošak rada po parceli.')}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" onClick={() => setWorkerFormOpen((v) => !v)}>
            {workerFormOpen ? tr('Zatvori radnika') : '+ Radnik'}
          </Button>
          <Button
            size="sm"
            onClick={() => {
              setEditingTask(null)
              setTaskFormOpen(true)
              setFormError(null)
            }}
          >
            + Zadatak
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Filteri</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <div className="space-y-1.5">
            <Label>{tr("Parcela")}</Label>
            <Select value={parcelId} onChange={(e) => setParcelId(e.target.value)}>
              <option value="">{tr('Sve parcele')}</option>
              {parcels.map((parcel) => (
                <option key={parcel.id} value={parcel.id}>
                  {parcel.name}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>Radnik</Label>
            <Select value={workerId} onChange={(e) => setWorkerId(e.target.value)}>
              <option value="">{tr('Svi radnici')}</option>
              {workers.map((worker) => (
                <option key={worker.id} value={worker.id}>
                  {workerLabel(worker)}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>Tip zadatka</Label>
            <Select value={taskTypeId} onChange={(e) => setTaskTypeId(e.target.value)}>
              <option value="">{tr('Svi tipovi')}</option>
              {types.map((type) => (
                <option key={type.id} value={type.id}>
                  {type.name}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>Od</Label>
            <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label>Do</Label>
            <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label={tr("Ukupan trošak rada")} value={formatMoney(dashboard?.total_labor_cost)} />
        <Stat label="Ukupno sati" value={formatNumber(Number(dashboard?.total_hours ?? 0))} />
        <Stat label="Aktivni radnici" value={formatNumber(dashboard?.worker_count ?? 0)} />
        <Stat label={tr("Završeni zadaci")} value={formatNumber(dashboard?.task_count ?? 0)} />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Breakdown title={tr('Po radniku')} items={dashboard?.by_worker ?? []} />
        <Breakdown title={tr('Po tipu zadatka')} items={dashboard?.by_task_type ?? []} />
        <Breakdown title={tr('Po parceli')} items={dashboard?.by_parcel ?? []} />
      </div>

      {workerFormOpen ? (
        <WorkerForm
          onCancel={() => setWorkerFormOpen(false)}
          error={formError}
          pending={createWorkerMutation.isPending}
          onSubmit={(payload) => {
            setFormError(null)
            createWorkerMutation.mutate(payload)
          }}
        />
      ) : null}

      {taskFormOpen ? (
        <TaskForm
          workers={activeWorkers.length ? activeWorkers : workers}
          parcels={parcels}
          types={types}
          initial={editingTask}
          defaultParcelId={parcelId}
          error={formError}
          pending={saveTaskMutation.isPending}
          onCancel={() => {
            setTaskFormOpen(false)
            setEditingTask(null)
            setFormError(null)
          }}
          onSubmit={(payload) => {
            setFormError(null)
            saveTaskMutation.mutate(payload)
          }}
        />
      ) : null}

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Radnici</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {workers.length === 0 ? (
            <p className="text-sm text-muted-foreground">{tr('Još nema evidentiranih radnika.')}</p>
          ) : (
            workers.map((worker) => (
              <div
                key={worker.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border px-3 py-2"
              >
                <div>
                  <p className="text-sm font-medium">{workerLabel(worker)}</p>
                  <p className="text-xs text-muted-foreground">
                    {formatMoney(worker.hourly_rate)} / h · {worker.active ? 'aktivan' : 'neaktivan'}
                  </p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => updateWorkerMutation.mutate({ id: worker.id, active: !worker.active })}
                >
                  {worker.active ? tr('Deaktiviraj') : 'Aktiviraj'}
                </Button>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Zadaci</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {tasksQuery.isLoading ? (
            <p className="text-sm text-muted-foreground">{tr('Učitavanje…')}</p>
          ) : tasks.length === 0 ? (
            <p className="text-sm text-muted-foreground">{tr('Nema zadataka za izabrane filtere.')}</p>
          ) : (
            tasks.map((task) => (
              <div
                key={task.id}
                className="flex flex-col gap-2 rounded-lg border border-border px-3 py-3 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="min-w-0 space-y-0.5">
                  <p className="text-sm font-medium">
                    {task.task_type?.name ?? 'Zadatak'} · {task.worker_name ?? 'Radnik'}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {formatDate(task.worked_on)}
                    {task.parcel_name ? tr(' · {{name}}', { name: task.parcel_name }) : ''}
                    {` · ${formatNumber(Number(task.hours))} h × ${formatMoney(task.hourly_rate_snapshot)}`}
                    {` · ${statusLabel(task.status)}`}
                  </p>
                  <p className="text-sm font-semibold">{formatMoney(task.labor_cost)}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {task.parcel_id ? (
                    <Link to={`/orchard/${task.parcel_id}`}>
                      <Button variant="outline" size="sm">
                        {tr("Parcela")}
                      </Button>
                    </Link>
                  ) : null}
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setEditingTask(task)
                      setTaskFormOpen(true)
                      setFormError(null)
                    }}
                  >
                    Izmeni
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      if (window.confirm(tr('Obrisati zadatak?'))) deleteTaskMutation.mutate(task.id)
                    }}
                  >
                    {tr("Obriši")}
                  </Button>
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <article className="rounded-xl border border-border bg-card p-4">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="mt-2 text-xl font-semibold tracking-tight">{value}</p>
    </article>
  )
}

function Breakdown({
  title,
  items,
}: {
  title: string
  items: { label: string; hours: string; labor_cost: string; task_count: number }[]
}) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {items.length === 0 ? (
          <p className="text-sm text-muted-foreground">{tr('Nema podataka.')}</p>
        ) : (
          items.map((item) => (
            <div key={`${title}-${item.label}`} className="flex items-start justify-between gap-3 text-sm">
              <div className="min-w-0">
                <p className="truncate font-medium">{item.label}</p>
                <p className="text-xs text-muted-foreground">
                  {formatNumber(Number(item.hours))} h · {item.task_count} zad.
                </p>
              </div>
              <p className="shrink-0 font-semibold">{formatMoney(item.labor_cost)}</p>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  )
}

function WorkerForm({
  onSubmit,
  onCancel,
  pending,
  error,
}: {
  onSubmit: (payload: { first_name: string; last_name: string; hourly_rate: string }) => void
  onCancel: () => void
  pending: boolean
  error: string | null
}) {
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [hourlyRate, setHourlyRate] = useState('10')

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    onSubmit({ first_name: firstName.trim(), last_name: lastName.trim(), hourly_rate: hourlyRate })
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Novi radnik</CardTitle>
      </CardHeader>
      <CardContent>
        <form className="grid gap-3 sm:grid-cols-3" onSubmit={handleSubmit}>
          <div className="space-y-1.5">
            <Label>Ime</Label>
            <Input value={firstName} onChange={(e) => setFirstName(e.target.value)} required />
          </div>
          <div className="space-y-1.5">
            <Label>Prezime</Label>
            <Input value={lastName} onChange={(e) => setLastName(e.target.value)} required />
          </div>
          <div className="space-y-1.5">
            <Label>Satnica (EUR)</Label>
            <Input
              type="number"
              min="0.01"
              step="0.01"
              value={hourlyRate}
              onChange={(e) => setHourlyRate(e.target.value)}
              required
            />
          </div>
          {error ? <p className="text-sm text-danger sm:col-span-3">{error}</p> : null}
          <div className="flex gap-2 sm:col-span-3">
            <Button type="submit" disabled={pending}>
              {tr("Sačuvaj")}
            </Button>
            <Button type="button" variant="outline" onClick={onCancel}>
              {tr('Otkaži')}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}

function TaskForm({
  workers,
  parcels,
  types,
  initial,
  defaultParcelId,
  onSubmit,
  onCancel,
  pending,
  error,
}: {
  workers: Worker[]
  parcels: { id: string; name: string }[]
  types: { id: string; name: string }[]
  initial: WorkTask | null
  defaultParcelId: string
  onSubmit: (payload: {
    worker_id: string
    parcel_id: string
    task_type_id: string
    description: string
    worked_on: string
    hours: string
    hourly_rate: string
    status: WorkTaskStatus
  }) => void
  onCancel: () => void
  pending: boolean
  error: string | null
}) {
  const [selectedWorkerId, setSelectedWorkerId] = useState(initial?.worker_id || workers[0]?.id || '')
  const [selectedParcelId, setSelectedParcelId] = useState(
    initial?.parcel_id || defaultParcelId || parcels[0]?.id || '',
  )
  const [selectedTypeId, setSelectedTypeId] = useState(initial?.task_type_id || types[0]?.id || '')
  const [workedOn, setWorkedOn] = useState(initial?.worked_on || todayKey())
  const [hours, setHours] = useState(initial?.hours || '1')
  const [hourlyRate, setHourlyRate] = useState(initial?.hourly_rate_snapshot || '')
  const [description, setDescription] = useState(initial?.description || '')
  const [status, setStatus] = useState<WorkTaskStatus>(initial?.status || 'completed')

  useEffect(() => {
    if (initial) return
    const worker = workers.find((item) => item.id === selectedWorkerId)
    if (worker) setHourlyRate(worker.hourly_rate)
  }, [selectedWorkerId, workers, initial])

  const laborCost = useMemo(() => {
    const h = Number(hours)
    const r = Number(hourlyRate)
    if (!Number.isFinite(h) || !Number.isFinite(r)) return null
    return (h * r).toFixed(2)
  }, [hours, hourlyRate])

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    onSubmit({
      worker_id: selectedWorkerId,
      parcel_id: selectedParcelId,
      task_type_id: selectedTypeId,
      description: description.trim(),
      worked_on: workedOn,
      hours,
      hourly_rate: hourlyRate,
      status,
    })
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">{initial ? tr('Izmena zadatka') : 'Novi zadatak'}</CardTitle>
      </CardHeader>
      <CardContent>
        <form className="grid gap-3 sm:grid-cols-2" onSubmit={handleSubmit}>
          <div className="space-y-1.5">
            <Label>Radnik</Label>
            <Select value={selectedWorkerId} onChange={(e) => setSelectedWorkerId(e.target.value)} required>
              {workers.map((worker) => (
                <option key={worker.id} value={worker.id}>
                  {workerLabel(worker)}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>{tr("Parcela")}</Label>
            <Select value={selectedParcelId} onChange={(e) => setSelectedParcelId(e.target.value)} required>
              {parcels.map((parcel) => (
                <option key={parcel.id} value={parcel.id}>
                  {parcel.name}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>Tip zadatka</Label>
            <Select value={selectedTypeId} onChange={(e) => setSelectedTypeId(e.target.value)} required>
              {types.map((type) => (
                <option key={type.id} value={type.id}>
                  {type.name}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>Datum</Label>
            <Input type="date" value={workedOn} onChange={(e) => setWorkedOn(e.target.value)} required />
          </div>
          <div className="space-y-1.5">
            <Label>Sati</Label>
            <Input
              type="number"
              min="0.01"
              step="0.01"
              value={hours}
              onChange={(e) => setHours(e.target.value)}
              required
            />
          </div>
          <div className="space-y-1.5">
            <Label>Satnica (EUR)</Label>
            <Input
              type="number"
              min="0.01"
              step="0.01"
              value={hourlyRate}
              onChange={(e) => setHourlyRate(e.target.value)}
              required
            />
          </div>
          <div className="space-y-1.5">
            <Label>Status</Label>
            <Select value={status} onChange={(e) => setStatus(e.target.value as WorkTaskStatus)}>
              <option value="completed">{tr("Završeno")}</option>
              <option value="planned">{tr("Planirano")}</option>
              <option value="cancelled">{tr("Otkazano")}</option>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>{tr('Trošak rada')}</Label>
            <Input value={laborCost ?? '—'} readOnly />
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label>Opis</Label>
            <Textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2} />
          </div>
          {error ? <p className="text-sm text-danger sm:col-span-2">{error}</p> : null}
          <div className="flex gap-2 sm:col-span-2">
            <Button type="submit" disabled={pending || !selectedWorkerId || !selectedParcelId || !selectedTypeId}>
              {tr("Sačuvaj")}
            </Button>
            <Button type="button" variant="outline" onClick={onCancel}>
              {tr('Otkaži')}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}
