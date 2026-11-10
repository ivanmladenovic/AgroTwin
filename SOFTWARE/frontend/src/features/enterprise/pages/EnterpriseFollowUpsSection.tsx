import { useState, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import {
  createEnterpriseFollowUp,
  listEnterpriseFollowUps,
  listEnterpriseMemberships,
  listEnterpriseParcels,
  updateEnterpriseFollowUp,
} from '@/features/enterprise/api'
import { useEnterprise } from '@/features/enterprise/EnterpriseContext'
import { formatDate } from '@/shared/lib/format'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { Select } from '@/shared/ui/select'

import { tr } from '@/shared/i18n/i18n'

const STATUS_LABEL_KEYS: Record<string, string> = {
  open: 'Otvoren',
  in_progress: 'U toku',
  completed: 'Završen',
  cancelled: 'Otkazan',
}

export function EnterpriseFollowUpsSection() {
  useTranslation()
  const { organizationId, canWritePlans } = useEnterprise()
  const queryClient = useQueryClient()
  const [status, setStatus] = useState('')
  const [due, setDue] = useState('')
  const [farmId, setFarmId] = useState('')
  const [parcelId, setParcelId] = useState('')
  const [assigneeId, setAssigneeId] = useState('')
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [dueOn, setDueOn] = useState('')
  const [newParcelId, setNewParcelId] = useState('')
  const [newAssigneeId, setNewAssigneeId] = useState('')
  const [error, setError] = useState<string | null>(null)

  const tasksQuery = useQuery({
    queryKey: ['enterprise-follow-ups', organizationId, status, due, farmId, parcelId, assigneeId],
    queryFn: () =>
      listEnterpriseFollowUps(organizationId, {
        status: status || undefined,
        due: due || undefined,
        farm_id: farmId || undefined,
        parcel_id: parcelId || undefined,
        assignee_user_id: assigneeId || undefined,
      }),
  })
  const parcelsQuery = useQuery({
    queryKey: ['enterprise-parcels', organizationId],
    queryFn: () => listEnterpriseParcels(organizationId),
  })
  const membersQuery = useQuery({
    queryKey: ['enterprise-members', organizationId],
    queryFn: () => listEnterpriseMemberships(organizationId),
  })

  const parcels = parcelsQuery.data ?? []
  const members = (membersQuery.data ?? []).filter((member) => member.status === 'active')
  const farms = new Map<string, string>()
  for (const parcel of parcels) {
    farms.set(parcel.farm_id, parcel.producer_display_name || parcel.farm_name)
  }

  const createTask = useMutation({
    mutationFn: () => {
      const parcel = parcels.find((item) => item.parcel_id === newParcelId)
      return createEnterpriseFollowUp(organizationId, {
        title: title.trim(),
        body: body.trim() || null,
        due_on: dueOn || null,
        status: 'open',
        parcel_id: newParcelId || null,
        farm_id: parcel?.farm_id ?? null,
        assignee_user_id: newAssigneeId || null,
      })
    },
    onSuccess: async () => {
      setTitle('')
      setBody('')
      setDueOn('')
      setNewParcelId('')
      setNewAssigneeId('')
      setError(null)
      await queryClient.invalidateQueries({ queryKey: ['enterprise-follow-ups', organizationId] })
    },
    onError: (err: Error) => setError(err.message),
  })

  const updateTask = useMutation({
    mutationFn: (payload: { id: string; status: string }) =>
      updateEnterpriseFollowUp(organizationId, payload.id, { status: payload.status }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['enterprise-follow-ups', organizationId] })
    },
  })

  const tasks = tasksQuery.data ?? []
  const visibleParcels = parcels.filter((parcel) => !farmId || parcel.farm_id === farmId)

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        {tr('Interni zadaci kompanije. Ne upisuju se u dnevnik proizvođača i ne menjaju status upozorenja.')}
        {tr('„Rok se približava“ znači narednih 7 dana.')}
      </p>
      <div className="flex flex-wrap gap-3">
        <Filter label="Status">
          <Select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">Svi</option>
            {Object.entries(STATUS_LABEL_KEYS).map(([value, label]) => (
              <option key={value} value={value}>
                {tr(label)}
              </option>
            ))}
          </Select>
        </Filter>
        <Filter label="Rok">
          <Select value={due} onChange={(e) => setDue(e.target.value)}>
            <option value="">Svi</option>
            <option value="overdue">Istekao</option>
            <option value="upcoming">Narednih 7 dana</option>
          </Select>
        </Filter>
        <Filter label={tr("Dobavljač")}>
          <Select
            value={farmId}
            onChange={(e) => {
              setFarmId(e.target.value)
              setParcelId('')
            }}
          >
            <option value="">Svi</option>
            {[...farms.entries()].map(([id, name]) => (
              <option key={id} value={id}>
                {name}
              </option>
            ))}
          </Select>
        </Filter>
        <Filter label={tr("Parcela")}>
          <Select value={parcelId} onChange={(e) => setParcelId(e.target.value)}>
            <option value="">Sve</option>
            {visibleParcels.map((parcel) => (
              <option key={parcel.parcel_id} value={parcel.parcel_id}>
                {parcel.parcel_name}
              </option>
            ))}
          </Select>
        </Filter>
        <Filter label="Odgovorno lice">
          <Select value={assigneeId} onChange={(e) => setAssigneeId(e.target.value)}>
            <option value="">Svi</option>
            {members.map((member) => (
              <option key={member.user_id} value={member.user_id}>
                {member.user_full_name || member.user_email}
              </option>
            ))}
          </Select>
        </Filter>
      </div>
      {canWritePlans ? (
        <form
          className="grid gap-3 rounded-2xl border border-border p-4 sm:grid-cols-2"
          onSubmit={(event) => {
            event.preventDefault()
            createTask.mutate()
          }}
        >
          <div className="space-y-1.5 sm:col-span-2">
            <Label>Naslov</Label>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} required />
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label>Opis</Label>
            <Input value={body} onChange={(e) => setBody(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label>{tr("Parcela")}</Label>
            <Select value={newParcelId} onChange={(e) => setNewParcelId(e.target.value)}>
              <option value="">{tr('Bez parcele')}</option>
              {parcels.map((parcel) => (
                <option key={parcel.parcel_id} value={parcel.parcel_id}>
                  {parcel.parcel_name}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>Odgovorno lice</Label>
            <Select value={newAssigneeId} onChange={(e) => setNewAssigneeId(e.target.value)}>
              <option value="">{tr('Nije dodeljeno')}</option>
              {members.map((member) => (
                <option key={member.user_id} value={member.user_id}>
                  {member.user_full_name || member.user_email}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>Rok</Label>
            <Input type="date" value={dueOn} onChange={(e) => setDueOn(e.target.value)} />
          </div>
          {error ? <p className="text-sm text-danger sm:col-span-2">{error}</p> : null}
          <div className="sm:col-span-2">
            <Button type="submit" disabled={createTask.isPending || !title.trim()}>
              Novi zadatak
            </Button>
          </div>
        </form>
      ) : (
        <p className="text-sm text-muted-foreground">Imate samo pregled zadataka.</p>
      )}
      {tasksQuery.isLoading ? (
        <p className="text-sm text-muted-foreground">{tr('Učitavanje zadataka…')}</p>
      ) : tasksQuery.isError ? (
        <p className="text-sm text-danger">{tr('Zadaci nisu učitani.')}</p>
      ) : tasks.length === 0 ? (
        <p className="text-sm text-muted-foreground">{tr('Nema zadataka za izabrani filter.')}</p>
      ) : (
        <ul className="space-y-2">
          {tasks.map((task) => (
            <li key={task.id} className="rounded-2xl border border-border px-4 py-3 text-sm">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="font-medium">{task.title}</p>
                  {task.body ? <p className="mt-1 text-muted-foreground">{task.body}</p> : null}
                  <p className="mt-1 text-xs text-muted-foreground">
                    {task.parcel_name || task.farm_name || tr('Bez parcele')}
                    {task.due_on ? ` · rok ${formatDate(task.due_on)}` : ''}
                    {task.assignee_name ? ` · ${task.assignee_name}` : ''}
                  </p>
                </div>
                {canWritePlans ? (
                  <Select
                    className="w-36"
                    value={task.status}
                    onChange={(e) => updateTask.mutate({ id: task.id, status: e.target.value })}
                  >
                    {Object.entries(STATUS_LABEL_KEYS).map(([value, label]) => (
                      <option key={value} value={value}>
                        {tr(label)}
                      </option>
                    ))}
                  </Select>
                ) : (
                  <span className="text-xs text-muted-foreground">
                    {tr(STATUS_LABEL_KEYS[task.status] ?? task.status)}
                  </span>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function Filter({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="min-w-[9rem] space-y-1">
      <Label>{label}</Label>
      {children}
    </div>
  )
}
