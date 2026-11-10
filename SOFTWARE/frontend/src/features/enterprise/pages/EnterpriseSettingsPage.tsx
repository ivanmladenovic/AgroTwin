import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQueryClient } from '@tanstack/react-query'

import { updateEnterpriseOrganization } from '@/features/enterprise/api'
import { EnterpriseMembersSection } from '@/features/enterprise/pages/EnterpriseMembersSection'
import { useEnterprise } from '@/features/enterprise/EnterpriseContext'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { tr } from '@/shared/i18n/i18n'

export function EnterpriseSettingsPage() {
  useTranslation()
  const { organizationId, organization, membership, isAdmin } = useEnterprise()
  const queryClient = useQueryClient()
  const [orgName, setOrgName] = useState(organization?.name ?? '')
  const [description, setDescription] = useState(organization?.description ?? '')
  const [country, setCountry] = useState(organization?.country ?? '')
  const [currency, setCurrency] = useState(organization?.default_currency ?? 'RSD')
  const [timezone, setTimezone] = useState(organization?.timezone ?? '')
  const [defaultCrop, setDefaultCrop] = useState(organization?.default_crop ?? '')

  useEffect(() => {
    if (!organization) return
    setOrgName(organization.name ?? '')
    setDescription(organization.description ?? '')
    setCountry(organization.country ?? '')
    setCurrency(organization.default_currency ?? 'RSD')
    setTimezone(organization.timezone ?? '')
    setDefaultCrop(organization.default_crop ?? '')
  }, [organization])

  const saveOrg = useMutation({
    mutationFn: () =>
      updateEnterpriseOrganization(organizationId, {
        name: orgName,
        description: description || null,
        country: country || null,
        default_currency: currency || undefined,
        timezone: timezone || null,
        default_crop: defaultCrop || null,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['enterprise-org', organizationId] })
    },
  })

  if (!isAdmin) {
    return (
      <div className="space-y-3">
        <p className="kicker">{tr("Podešavanja")}</p>
        <h1 className="text-2xl font-semibold">Organizacija</h1>
        <p className="text-sm text-muted-foreground">
          {tr('Uloga: {{role}}. Samo Enterprise administrator može menjati opšte informacije.', {
            role: membership?.role ?? '—',
          })}
        </p>
        <dl className="grid gap-3 rounded-2xl border border-border px-4 py-4 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-xs text-muted-foreground">Naziv</dt>
            <dd className="font-medium">{organization?.name}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Valuta</dt>
            <dd className="font-medium">{organization?.default_currency}</dd>
          </div>
          {organization?.country ? (
            <div>
              <dt className="text-xs text-muted-foreground">{tr('Država')}</dt>
              <dd className="font-medium">{organization.country}</dd>
            </div>
          ) : null}
          {organization?.description ? (
            <div className="sm:col-span-2">
              <dt className="text-xs text-muted-foreground">Opis</dt>
              <dd className="font-medium">{organization.description}</dd>
            </div>
          ) : null}
        </dl>
        <EnterpriseMembersSection />
      </div>
    )
  }

  return (
    <div className="space-y-8">
      <div>
        <p className="kicker">{tr("Podešavanja")}</p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">{tr('Opšte informacije')}</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {tr('Povezivanje dobavljača i parcela radi AgroTwin tim. Ovde menjate samo podatke organizacije.')}
        </p>
      </div>

      <section className="space-y-4 rounded-2xl border border-border p-4 sm:p-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5 sm:col-span-2">
            <Label>{tr('Naziv organizacije')}</Label>
            <Input value={orgName} onChange={(e) => setOrgName(e.target.value)} />
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label>Opis</Label>
            <Input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder={tr('Kratak opis organizacije')}
            />
          </div>
          <div className="space-y-1.5">
            <Label>{tr('Država')}</Label>
            <Input value={country} onChange={(e) => setCountry(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label>Valuta</Label>
            <Input value={currency} onChange={(e) => setCurrency(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label>Vremenska zona</Label>
            <Input
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
              placeholder="Europe/Belgrade"
            />
          </div>
          <div className="space-y-1.5">
            <Label>Podrazumevani usev</Label>
            <Input
              value={defaultCrop}
              onChange={(e) => setDefaultCrop(e.target.value)}
              placeholder="npr. leska"
            />
          </div>
        </div>
        <Button type="button" onClick={() => saveOrg.mutate()} disabled={saveOrg.isPending || !orgName.trim()}>
          {tr("Sačuvaj izmene")}
        </Button>
        {saveOrg.isSuccess ? (
          <p className="text-sm text-emerald-700">{tr('Sačuvano.')}</p>
        ) : null}
        {saveOrg.isError ? (
          <p className="text-sm text-danger">{tr("Čuvanje nije uspelo.")}</p>
        ) : null}
      </section>
      <EnterpriseMembersSection />
    </div>
  )
}
