import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'

import {
  assignAdminParcels,
  deactivateAdminAssignment,
  linkAdminFarm,
  listAdminEnterpriseOrgs,
  listAdminFarms,
  listAdminOrgAssignments,
  listAdminOrgSuppliers,
} from '@/features/admin/api'
import { formatNumber } from '@/shared/lib/format'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'

import { tr } from '@/shared/i18n/i18n'
export function AdminEnterpriseLinkPage() {
  const { organizationId = '' } = useParams()
  const queryClient = useQueryClient()
  const [farmFilter, setFarmFilter] = useState('')
  const [selectedParcels, setSelectedParcels] = useState<Record<string, boolean>>({})

  const orgsQuery = useQuery({
    queryKey: ['admin-enterprise-orgs'],
    queryFn: listAdminEnterpriseOrgs,
  })
  const org = (orgsQuery.data ?? []).find((item) => item.id === organizationId)

  const farmsQuery = useQuery({
    queryKey: ['admin-farms', organizationId],
    queryFn: () => listAdminFarms(organizationId),
    enabled: Boolean(organizationId),
  })
  const suppliersQuery = useQuery({
    queryKey: ['admin-org-suppliers', organizationId],
    queryFn: () => listAdminOrgSuppliers(organizationId),
    enabled: Boolean(organizationId),
  })
  const assignmentsQuery = useQuery({
    queryKey: ['admin-org-assignments', organizationId],
    queryFn: () => listAdminOrgAssignments(organizationId),
    enabled: Boolean(organizationId),
  })

  const farms = useMemo(() => {
    const needle = farmFilter.trim().toLowerCase()
    return (farmsQuery.data ?? []).filter((farm) => {
      if (!needle) return true
      const hay = `${farm.name} ${farm.owner_name ?? ''} ${farm.owner_email ?? ''}`.toLowerCase()
      return hay.includes(needle)
    })
  }, [farmsQuery.data, farmFilter])

  const invalidate = async () => {
    await queryClient.invalidateQueries({ queryKey: ['admin-farms', organizationId] })
    await queryClient.invalidateQueries({ queryKey: ['admin-org-suppliers', organizationId] })
    await queryClient.invalidateQueries({ queryKey: ['admin-org-assignments', organizationId] })
    await queryClient.invalidateQueries({ queryKey: ['admin-enterprise-orgs'] })
    await queryClient.invalidateQueries({ queryKey: ['admin-overview'] })
  }

  const linkFarm = useMutation({
    mutationFn: (payload: {
      farm_id: string
      assign_all_parcels?: boolean
      parcel_ids?: string[]
    }) => linkAdminFarm(organizationId, payload),
    onSuccess: async () => {
      setSelectedParcels({})
      await invalidate()
    },
  })

  const assignSelected = useMutation({
    mutationFn: (parcelIds: string[]) =>
      assignAdminParcels(organizationId, { parcel_ids: parcelIds }),
    onSuccess: async () => {
      setSelectedParcels({})
      await invalidate()
    },
  })

  const deactivate = useMutation({
    mutationFn: (assignmentId: string) =>
      deactivateAdminAssignment(organizationId, assignmentId),
    onSuccess: invalidate,
  })

  if (!organizationId) {
    return <p className="text-sm text-danger">{tr('Nedostaje organizacija.')}</p>
  }

  return (
    <div className="space-y-6">
      <div>
        <Link to="/admin" className="text-sm text-primary hover:underline">
          ← Nalozi
        </Link>
        <h1 className="mt-2 text-2xl font-semibold">
          {tr('Dobavljači → {{name}}', { name: org?.name ?? tr('Enterprise kompanija') })}
        </h1>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
          {tr(
            'Poveži dobavljača (osobu / firmu na klijentskom nalogu) sa ovom Enterprise kompanijom, pa odaberi parcele za koje dobijaju uvid. Proizvođač ostaje vlasnik podataka; Enterprise ima samo čitanje.',
          )}
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <Stat label={tr("Povezani dobavljači")} value={formatNumber(org?.supplier_count)} />
        <Stat label={tr('Parcele sa uvidom')} value={formatNumber(org?.assigned_parcel_count)} />
        <Stat label={tr("Članovi Enterprise")} value={formatNumber(org?.member_count)} />
      </div>

      <section className="space-y-3 rounded-xl border border-border p-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold">{tr('Dostupni dobavljači')}</h2>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {tr('Naziv je ime / firma naloga. Ispod su zasadi i parcele koje možeš dodeliti za uvid.')}
            </p>
          </div>
          <Input
            className="max-w-xs"
            placeholder={tr("Pretraga po imenu, firmi ili e-pošti")}
            value={farmFilter}
            onChange={(e) => setFarmFilter(e.target.value)}
          />
        </div>

        <ul className="space-y-3">
          {farms.map((farm) => {
            const selectedIds = farm.parcels
              .filter((parcel) => selectedParcels[parcel.parcel_id])
              .map((parcel) => parcel.parcel_id)
            const supplierTitle = farm.owner_name ?? farm.name
            return (
              <li key={farm.farm_id} className="rounded-lg border border-border p-3">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="font-medium">{supplierTitle}</p>
                    <p className="text-xs text-muted-foreground">
                      Zasad: {farm.name}
                      {farm.owner_email ? ` · ${farm.owner_email}` : ''}
                      {farm.linked_as_supplier ? tr(' · već povezan kao dobavljač') : ''}
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
                      className="flex items-center justify-between gap-3 rounded-md bg-muted/30 px-3 py-2 text-sm"
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
                    <li className="text-xs text-muted-foreground">{tr('Nema parcela na zasadu.')}</li>
                  ) : null}
                </ul>
              </li>
            )
          })}
          {farms.length === 0 ? (
            <li className="rounded-lg border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
              Nema klijentskih naloga za povezivanje.
            </li>
          ) : null}
        </ul>
      </section>

      <section className="rounded-xl border border-border">
        <div className="border-b border-border px-4 py-3">
          <h2 className="text-sm font-semibold">{tr('Parcele sa uvidom')}</h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {tr('Šta Enterprise kompanija trenutno može da vidi.')}
          </p>
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
                  {item.farm_name && item.owner_name ? ` · ${item.farm_name}` : ''} · {item.status}
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
              {tr('Još nema parcela sa uvidom za ovu kompaniju.')}
            </li>
          ) : null}
        </ul>
      </section>

      <section className="rounded-xl border border-border">
        <div className="border-b border-border px-4 py-3">
          <h2 className="text-sm font-semibold">{tr("Povezani dobavljači")}</h2>
        </div>
        <ul className="divide-y divide-border">
          {(suppliersQuery.data ?? []).map((link) => (
            <li key={link.id} className="px-4 py-3 text-sm">
              <p className="font-medium">{link.owner_name ?? link.farm_name}</p>
              <p className="text-xs text-muted-foreground">
                {link.farm_name && link.owner_name ? `${link.farm_name} · ` : ''}
                {link.owner_email ?? '—'} · {link.assigned_parcel_count} parcela sa uvidom ·{' '}
                {link.status}
              </p>
            </li>
          ))}
          {(suppliersQuery.data ?? []).length === 0 ? (
            <li className="px-4 py-6 text-sm text-muted-foreground">
              {tr('Nema povezanih dobavljača.')}
            </li>
          ) : null}
        </ul>
      </section>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border px-4 py-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-xl font-semibold tabular-nums">{value}</p>
    </div>
  )
}
