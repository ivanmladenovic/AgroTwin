import { useMemo, useState, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Pencil, Trash2, X } from 'lucide-react'

import {
  assignAdminParcels,
  createAdminClient,
  createAdminEnterpriseOrg,
  createAdminEnterpriseUser,
  deactivateAdminAssignment,
  deleteAdminUser,
  linkAdminFarm,
  listAdminEnterpriseOrgs,
  listAdminFarms,
  listAdminOrgAssignments,
  listAdminUsers,
  updateAdminUser,
} from '@/features/admin/api'
import type { AdminUserSummary } from '@/shared/api/types'
import { formatNumber } from '@/shared/lib/format'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { Select } from '@/shared/ui/select'

import { tr } from '@/shared/i18n/i18n'
function kindLabel(kind: string) {
  if (kind === 'platform_admin') return 'Admin'
  if (kind === 'enterprise') return 'Enterprise'
  return 'Klijent'
}

export function AdminAccountsPage() {
  const queryClient = useQueryClient()
  const [q, setQ] = useState('')
  const [linkOrgId, setLinkOrgId] = useState('')
  const [selectedParcels, setSelectedParcels] = useState<Record<string, boolean>>({})
  const [editingUser, setEditingUser] = useState<AdminUserSummary | null>(null)
  const [editForm, setEditForm] = useState({
    full_name: '',
    email: '',
    is_active: true,
    temporary_password: '',
  })
  const [listFeedback, setListFeedback] = useState<string | null>(null)

  const usersQuery = useQuery({
    queryKey: ['admin-users', q],
    queryFn: () => listAdminUsers(q || undefined),
  })
  const orgsQuery = useQuery({
    queryKey: ['admin-enterprise-orgs'],
    queryFn: listAdminEnterpriseOrgs,
  })

  const [clientForm, setClientForm] = useState({
    email: '',
    full_name: '',
    temporary_password: '',
    farm_name: '',
    location_name: '',
  })
  const [enterpriseForm, setEnterpriseForm] = useState({
    company_name: '',
    email: '',
    full_name: '',
    temporary_password: '',
    role: 'enterprise_admin',
  })

  const orgs = orgsQuery.data ?? []
  const effectiveLinkOrgId = linkOrgId || orgs[0]?.id || ''

  const farmsQuery = useQuery({
    queryKey: ['admin-farms', effectiveLinkOrgId],
    queryFn: () => listAdminFarms(effectiveLinkOrgId),
    enabled: Boolean(effectiveLinkOrgId),
  })
  const assignmentsQuery = useQuery({
    queryKey: ['admin-org-assignments', effectiveLinkOrgId],
    queryFn: () => listAdminOrgAssignments(effectiveLinkOrgId),
    enabled: Boolean(effectiveLinkOrgId),
  })

  const invalidateAccounts = async () => {
    await queryClient.invalidateQueries({ queryKey: ['admin-users'] })
    await queryClient.invalidateQueries({ queryKey: ['admin-enterprise-orgs'] })
    await queryClient.invalidateQueries({ queryKey: ['admin-overview'] })
  }

  const invalidateLinking = async () => {
    await invalidateAccounts()
    await queryClient.invalidateQueries({ queryKey: ['admin-farms'] })
    await queryClient.invalidateQueries({ queryKey: ['admin-org-assignments'] })
    await queryClient.invalidateQueries({ queryKey: ['admin-org-suppliers'] })
  }

  const createClient = useMutation({
    mutationFn: () =>
      createAdminClient({
        ...clientForm,
        farm_name: clientForm.farm_name || undefined,
        location_name: clientForm.location_name || undefined,
      }),
    onSuccess: async () => {
      setClientForm({
        email: '',
        full_name: '',
        temporary_password: '',
        farm_name: '',
        location_name: '',
      })
      await invalidateAccounts()
    },
  })

  const createEnterprise = useMutation({
    mutationFn: async () => {
      const org = await createAdminEnterpriseOrg({
        name: enterpriseForm.company_name.trim(),
        country: 'Srbija',
      })
      await createAdminEnterpriseUser({
        organization_id: org.id,
        email: enterpriseForm.email,
        full_name: enterpriseForm.full_name,
        temporary_password: enterpriseForm.temporary_password,
        role: enterpriseForm.role,
      })
      return org
    },
    onSuccess: async (org) => {
      setEnterpriseForm({
        company_name: '',
        email: '',
        full_name: '',
        temporary_password: '',
        role: 'enterprise_admin',
      })
      setLinkOrgId(org.id)
      await invalidateAccounts()
    },
  })

  const linkFarm = useMutation({
    mutationFn: (payload: {
      farm_id: string
      assign_all_parcels?: boolean
      parcel_ids?: string[]
    }) => linkAdminFarm(effectiveLinkOrgId, payload),
    onSuccess: async () => {
      setSelectedParcels({})
      await invalidateLinking()
    },
  })

  const assignSelected = useMutation({
    mutationFn: (parcelIds: string[]) =>
      assignAdminParcels(effectiveLinkOrgId, { parcel_ids: parcelIds }),
    onSuccess: async () => {
      setSelectedParcels({})
      await invalidateLinking()
    },
  })

  const deactivate = useMutation({
    mutationFn: (assignmentId: string) =>
      deactivateAdminAssignment(effectiveLinkOrgId, assignmentId),
    onSuccess: invalidateLinking,
  })

  const updateUser = useMutation({
    mutationFn: () => {
      if (!editingUser) throw new Error(tr('Nalog nije izabran'))
      return updateAdminUser(editingUser.id, {
        full_name: editForm.full_name.trim(),
        email: editForm.email.trim(),
        is_active: editForm.is_active,
        temporary_password: editForm.temporary_password.trim() || undefined,
      })
    },
    onSuccess: async () => {
      setEditingUser(null)
      setEditForm({ full_name: '', email: '', is_active: true, temporary_password: '' })
      setListFeedback(tr('Nalog je sačuvan.'))
      await invalidateAccounts()
    },
  })

  const deleteUser = useMutation({
    mutationFn: (userId: string) => deleteAdminUser(userId),
    onSuccess: async (result) => {
      if (editingUser?.id === result.id) {
        setEditingUser(null)
      }
      setListFeedback(result.message)
      await invalidateAccounts()
    },
  })

  function openEdit(user: AdminUserSummary) {
    setListFeedback(null)
    setEditingUser(user)
    setEditForm({
      full_name: user.full_name,
      email: user.email,
      is_active: user.is_active,
      temporary_password: '',
    })
  }

  function confirmDelete(user: AdminUserSummary) {
    const label = user.full_name || user.email
    const hint =
      user.farm_count > 0
        ? tr(' Nalog ima zasade — biće deaktiviran umesto trajnog brisanja.')
        : tr(' Ovo trajno briše nalog.')
    if (!window.confirm(tr('Obrisati nalog „{{label}}”?{{hint}}', { label, hint }))) return
    setListFeedback(null)
    deleteUser.mutate(user.id)
  }

  const selectedOrg = orgs.find((org) => org.id === effectiveLinkOrgId)
  const allUsers = usersQuery.data ?? []
  const farms = farmsQuery.data ?? []

  const clientsWithoutSuperuser = useMemo(
    () => allUsers.filter((u) => u.account_kinds.includes('client')),
    [allUsers],
  )

  return (
    <div className="space-y-10">
      <div>
        <p className="kicker">Platforma</p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">Upravljanje nalozima</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
          1) Napravi klijentske i Enterprise naloge · 2) Pregledaj spisak · 3) Izaberi Enterprise
          kompaniju i dodeli joj klijente (parcele) za uvid.
        </p>
      </div>

      {/* 1. Create accounts */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold tracking-tight">1. Novi nalozi</h2>
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="space-y-3 rounded-2xl border border-border p-4">
            <div>
              <h3 className="text-sm font-semibold">Klijentski nalog</h3>
              <p className="mt-0.5 text-xs text-muted-foreground">
                {tr('Proizvođač / dobavljač — radi u AgroTwin prostoru (zasadi, berba…).')}
              </p>
            </div>
            <Field label={tr('Ime i prezime / firma')}>
              <Input
                value={clientForm.full_name}
                onChange={(e) => setClientForm((p) => ({ ...p, full_name: e.target.value }))}
              />
            </Field>
            <Field label={tr("E-pošta")}>
              <Input
                type="email"
                value={clientForm.email}
                onChange={(e) => setClientForm((p) => ({ ...p, email: e.target.value }))}
              />
            </Field>
            <Field label="Lozinka">
              <Input
                type="password"
                value={clientForm.temporary_password}
                onChange={(e) =>
                  setClientForm((p) => ({ ...p, temporary_password: e.target.value }))
                }
              />
            </Field>
            <Field label={tr('Naziv zasada (opciono)')}>
              <Input
                value={clientForm.farm_name}
                onChange={(e) => setClientForm((p) => ({ ...p, farm_name: e.target.value }))}
              />
            </Field>
            <Field label={tr('Lokacija (opciono)')}>
              <Input
                value={clientForm.location_name}
                onChange={(e) => setClientForm((p) => ({ ...p, location_name: e.target.value }))}
              />
            </Field>
            <Button
              type="button"
              onClick={() => createClient.mutate()}
              disabled={
                !clientForm.email ||
                !clientForm.full_name ||
                clientForm.temporary_password.length < 8 ||
                createClient.isPending
              }
            >
              Kreiraj klijentski nalog
            </Button>
            {createClient.isError ? (
              <p className="text-sm text-danger">{(createClient.error as Error).message}</p>
            ) : null}
            {createClient.isSuccess ? (
              <p className="text-sm text-emerald-700">{tr('Klijentski nalog je kreiran.')}</p>
            ) : null}
          </div>

          <div className="space-y-3 rounded-2xl border border-border p-4">
            <div>
              <h3 className="text-sm font-semibold">Enterprise nalog</h3>
              <p className="mt-0.5 text-xs text-muted-foreground">
                {tr('Kompanija + prvi korisnik. Kasnije joj dodeljuješ uvid u klijentske parcele.')}
              </p>
            </div>
            <Field label={tr('Naziv kompanije')}>
              <Input
                value={enterpriseForm.company_name}
                onChange={(e) =>
                  setEnterpriseForm((p) => ({ ...p, company_name: e.target.value }))
                }
              />
            </Field>
            <Field label="Ime i prezime korisnika">
              <Input
                value={enterpriseForm.full_name}
                onChange={(e) => setEnterpriseForm((p) => ({ ...p, full_name: e.target.value }))}
              />
            </Field>
            <Field label={tr("E-pošta")}>
              <Input
                type="email"
                value={enterpriseForm.email}
                onChange={(e) => setEnterpriseForm((p) => ({ ...p, email: e.target.value }))}
              />
            </Field>
            <Field label="Uloga">
              <Select
                value={enterpriseForm.role}
                onChange={(e) => setEnterpriseForm((p) => ({ ...p, role: e.target.value }))}
              >
                <option value="enterprise_admin">Admin</option>
                <option value="enterprise_analyst">{tr('Analitičar')}</option>
                <option value="enterprise_viewer">{tr('Pregledač')}</option>
              </Select>
            </Field>
            <Field label="Lozinka">
              <Input
                type="password"
                value={enterpriseForm.temporary_password}
                onChange={(e) =>
                  setEnterpriseForm((p) => ({ ...p, temporary_password: e.target.value }))
                }
              />
            </Field>
            <Button
              type="button"
              onClick={() => createEnterprise.mutate()}
              disabled={
                !enterpriseForm.company_name.trim() ||
                !enterpriseForm.email ||
                !enterpriseForm.full_name ||
                enterpriseForm.temporary_password.length < 8 ||
                createEnterprise.isPending
              }
            >
              Kreiraj Enterprise nalog
            </Button>
            {createEnterprise.isError ? (
              <p className="text-sm text-danger">{(createEnterprise.error as Error).message}</p>
            ) : null}
            {createEnterprise.isSuccess ? (
              <p className="text-sm text-emerald-700">{tr('Enterprise nalog je kreiran.')}</p>
            ) : null}
          </div>
        </div>
      </section>

      {/* 2. Account list */}
      <section className="space-y-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <h2 className="text-lg font-semibold tracking-tight">2. Spisak naloga</h2>
          <Input
            className="max-w-xs"
            placeholder={tr("Pretraga po imenu ili e-pošti")}
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>

        {editingUser ? (
          <div className="space-y-3 rounded-2xl border border-border bg-muted/20 p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="text-sm font-semibold">{tr('Izmena naloga')}</h3>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {editingUser.account_kinds.map((kind) => kindLabel(kind)).join(', ')}
                  {editingUser.is_superuser ? ' · platform admin' : ''}
                </p>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                aria-label={tr('Zatvori izmenu')}
                onClick={() => setEditingUser(null)}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label={tr('Ime i prezime / firma')}>
                <Input
                  value={editForm.full_name}
                  onChange={(e) => setEditForm((p) => ({ ...p, full_name: e.target.value }))}
                />
              </Field>
              <Field label={tr("E-pošta")}>
                <Input
                  type="email"
                  value={editForm.email}
                  onChange={(e) => setEditForm((p) => ({ ...p, email: e.target.value }))}
                />
              </Field>
              <Field label={tr('Nova lozinka (opciono)')}>
                <Input
                  type="password"
                  value={editForm.temporary_password}
                  onChange={(e) =>
                    setEditForm((p) => ({ ...p, temporary_password: e.target.value }))
                  }
                  placeholder={tr("Ostavi prazno da ne menjaš")}
                />
              </Field>
              <Field label="Status">
                <Select
                  value={editForm.is_active ? 'active' : 'inactive'}
                  onChange={(e) =>
                    setEditForm((p) => ({ ...p, is_active: e.target.value === 'active' }))
                  }
                >
                  <option value="active">Aktivan</option>
                  <option value="inactive">Neaktivan</option>
                </Select>
              </Field>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                onClick={() => updateUser.mutate()}
                disabled={
                  !editForm.full_name.trim() ||
                  !editForm.email.trim() ||
                  (editForm.temporary_password.length > 0 &&
                    editForm.temporary_password.length < 8) ||
                  updateUser.isPending
                }
              >
                {tr('Sačuvaj izmene')}
              </Button>
              <Button type="button" variant="outline" onClick={() => setEditingUser(null)}>
                {tr('Otkaži')}
              </Button>
            </div>
            {updateUser.isError ? (
              <p className="text-sm text-danger">{(updateUser.error as Error).message}</p>
            ) : null}
          </div>
        ) : null}

        {listFeedback ? <p className="text-sm text-emerald-700">{listFeedback}</p> : null}
        {deleteUser.isError ? (
          <p className="text-sm text-danger">{(deleteUser.error as Error).message}</p>
        ) : null}

        <div className="overflow-x-auto rounded-2xl border border-border">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-border bg-muted/40 text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-3 py-2.5">Nalog</th>
                <th className="px-3 py-2.5">Tip</th>
                <th className="px-3 py-2.5">{tr('Zasadi')}</th>
                <th className="px-3 py-2.5">Enterprise kompanija</th>
                <th className="px-3 py-2.5">Status</th>
                <th className="px-3 py-2.5 text-right">Akcije</th>
              </tr>
            </thead>
            <tbody>
              {allUsers.map((user) => (
                <tr key={user.id} className="border-b border-border/70">
                  <td className="px-3 py-2.5">
                    <p className="font-medium">{user.full_name}</p>
                    <p className="text-xs text-muted-foreground">{user.email}</p>
                  </td>
                  <td className="px-3 py-2.5">
                    {user.account_kinds.map((kind) => kindLabel(kind)).join(', ')}
                  </td>
                  <td className="px-3 py-2.5 tabular-nums">{user.farm_count}</td>
                  <td className="px-3 py-2.5">
                    {user.enterprise_memberships.map((m) => m.organization_name).join(', ') ||
                      '—'}
                  </td>
                  <td className="px-3 py-2.5">{user.is_active ? tr('Aktivan') : 'Neaktivan'}</td>
                  <td className="px-3 py-2.5">
                    <div className="flex justify-end gap-1">
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        aria-label={`Izmeni ${user.full_name}`}
                        title="Izmeni"
                        onClick={() => openEdit(user)}
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="text-muted-foreground hover:text-danger"
                        aria-label={tr('Obriši {{name}}', { name: user.full_name })}
                        title={user.is_superuser ? tr('Platform admin se ne briše ovde') : tr('Obriši')}
                        disabled={user.is_superuser || deleteUser.isPending}
                        onClick={() => confirmDelete(user)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {allUsers.length === 0 ? (
            <p className="px-3 py-6 text-sm text-muted-foreground">{tr('Još nema naloga.')}</p>
          ) : null}
        </div>
        <p className="text-xs text-muted-foreground">
          Klijentskih: {clientsWithoutSuperuser.length} · Enterprise organizacija: {orgs.length}
        </p>
      </section>

      {/* 3. Linking */}
      <section className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">3. Povezivanje za uvid</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Izaberi Enterprise kompaniju, pa joj dodeli klijentske naloge i parcele koje sme da vidi.
          </p>
        </div>

        <div className="max-w-md space-y-1.5">
          <Label>Enterprise nalog / kompanija</Label>
          <Select
            value={effectiveLinkOrgId}
            onChange={(e) => {
              setLinkOrgId(e.target.value)
              setSelectedParcels({})
            }}
          >
            <option value="">{tr('Izaberite Enterprise…')}</option>
            {orgs.map((org) => (
              <option key={org.id} value={org.id}>
                {tr('{{name}} ({{suppliers}} dobavljača · {{parcels}} parcela)', {
                  name: org.name,
                  suppliers: org.supplier_count,
                  parcels: org.assigned_parcel_count,
                })}
              </option>
            ))}
          </Select>
        </div>

        {!effectiveLinkOrgId ? (
          <p className="rounded-2xl border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
            Prvo kreiraj Enterprise nalog, pa ga izaberi ovde.
          </p>
        ) : (
          <>
            <p className="text-sm text-muted-foreground">
              {tr('Dodeljuješ uvid za:')}{' '}
              <span className="font-semibold text-foreground">{selectedOrg?.name}</span>
            </p>

            <ul className="space-y-3">
              {farms.map((farm) => {
                const selectedIds = farm.parcels
                  .filter((parcel) => selectedParcels[parcel.parcel_id])
                  .map((parcel) => parcel.parcel_id)
                return (
                  <li key={farm.farm_id} className="rounded-2xl border border-border p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold">{farm.owner_name ?? farm.name}</p>
                        <p className="text-xs text-muted-foreground">
                          Zasad: {farm.name}
                          {farm.owner_email ? ` · ${farm.owner_email}` : ''}
                          {farm.linked_as_supplier ? tr(' · već povezan') : ''}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Button
                          type="button"
                          variant="outline"
                          onClick={() =>
                            linkFarm.mutate({
                              farm_id: farm.farm_id,
                              assign_all_parcels: true,
                            })
                          }
                          disabled={linkFarm.isPending}
                        >
                          {tr('Poveži + sve parcele')}
                        </Button>
                        <Button
                          type="button"
                          variant="outline"
                          onClick={() =>
                            linkFarm.mutate({
                              farm_id: farm.farm_id,
                              parcel_ids: selectedIds,
                            })
                          }
                          disabled={linkFarm.isPending || selectedIds.length === 0}
                        >
                          {tr('Poveži + izabrane ({{count}})', { count: selectedIds.length })}
                        </Button>
                        {farm.linked_as_supplier ? (
                          <Button
                            type="button"
                            variant="outline"
                            onClick={() => assignSelected.mutate(selectedIds)}
                            disabled={assignSelected.isPending || selectedIds.length === 0}
                          >
                            Dodaj uvid za izabrane
                          </Button>
                        ) : null}
                      </div>
                    </div>

                    <ul className="mt-3 space-y-1.5">
                      {farm.parcels.map((parcel) => (
                        <li
                          key={parcel.parcel_id}
                          className="flex items-center justify-between gap-3 rounded-xl bg-muted/30 px-3 py-2 text-sm"
                        >
                          <label className="flex min-w-0 items-center gap-2">
                            <input
                              type="checkbox"
                              checked={Boolean(selectedParcels[parcel.parcel_id])}
                              disabled={parcel.assigned_to_org}
                              onChange={(e) =>
                                setSelectedParcels((prev) => ({
                                  ...prev,
                                  [parcel.parcel_id]: e.target.checked,
                                }))
                              }
                            />
                            <span className="truncate">
                              {parcel.name}
                              {parcel.area_hectares != null
                                ? tr(' · {{area}} ha', { area: formatNumber(parcel.area_hectares) })
                                : ''}
                            </span>
                          </label>
                          <span className="shrink-0 text-xs text-muted-foreground">
                            {parcel.assigned_to_org ? 'Ima uvid' : tr('Bez uvida')}
                          </span>
                        </li>
                      ))}
                      {farm.parcels.length === 0 ? (
                        <li className="text-xs text-muted-foreground">{tr('Nema parcela.')}</li>
                      ) : null}
                    </ul>
                  </li>
                )
              })}
              {farms.length === 0 ? (
                <li className="rounded-2xl border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
                  Nema klijentskih naloga sa zasadima. Kreiraj klijenta u sekciji 1.
                </li>
              ) : null}
            </ul>

            <div className="rounded-2xl border border-border">
              <div className="border-b border-border px-4 py-3">
                <h3 className="text-sm font-semibold">
                  Parcele sa uvidom — {selectedOrg?.name ?? 'Enterprise'}
                </h3>
              </div>
              <ul className="divide-y divide-border">
                {(assignmentsQuery.data ?? []).map((item) => (
                  <li
                    key={item.id}
                    className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-sm"
                  >
                    <div>
                      <p className="font-medium">{item.parcel_name}</p>
                      <p className="text-xs text-muted-foreground">
                        {item.owner_name ?? item.farm_name ?? '—'}
                        {item.farm_name && item.owner_name ? ` · ${item.farm_name}` : ''}
                      </p>
                    </div>
                    {item.status === 'active' ? (
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => deactivate.mutate(item.id)}
                        disabled={deactivate.isPending}
                      >
                        Ukloni uvid
                      </Button>
                    ) : (
                      <span className="text-xs text-muted-foreground">Neaktivno</span>
                    )}
                  </li>
                ))}
                {(assignmentsQuery.data ?? []).length === 0 ? (
                  <li className="px-4 py-6 text-sm text-muted-foreground">
                    {tr('Još nema dodeljenih parcela za ovu kompaniju.')}
                  </li>
                ) : null}
              </ul>
            </div>
          </>
        )}
      </section>
    </div>
  )
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      {children}
    </div>
  )
}
