import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import {
  addEnterpriseMembership,
  listEnterpriseMemberships,
  updateEnterpriseMembership,
} from '@/features/enterprise/api'
import { useEnterprise } from '@/features/enterprise/EnterpriseContext'
import { formatDate } from '@/shared/lib/format'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { Select } from '@/shared/ui/select'
import type { EnterpriseMembershipRole } from '@/shared/api/types'

import { tr } from '@/shared/i18n/i18n'

const ROLE_LABEL_KEYS: Record<EnterpriseMembershipRole, string> = {
  enterprise_admin: 'Administrator',
  enterprise_analyst: 'Analitičar',
  enterprise_viewer: 'Pregled',
}

const STATUS_LABEL_KEYS = {
  active: 'Aktivan',
  inactive: 'Neaktivan',
  invited: 'Pozvan',
} as const

export function EnterpriseMembersSection() {
  useTranslation()
  const { organizationId, isAdmin } = useEnterprise()
  const queryClient = useQueryClient()
  const [email, setEmail] = useState('')
  const [fullName, setFullName] = useState('')
  const [role, setRole] = useState<EnterpriseMembershipRole>('enterprise_viewer')
  const [temporaryPassword, setTemporaryPassword] = useState('')
  const [formError, setFormError] = useState<string | null>(null)

  const membersQuery = useQuery({
    queryKey: ['enterprise-members', organizationId],
    queryFn: () => listEnterpriseMemberships(organizationId),
    enabled: isAdmin,
  })

  const addMember = useMutation({
    mutationFn: () =>
      addEnterpriseMembership(organizationId, {
        email: email.trim(),
        full_name: fullName.trim(),
        role,
        temporary_password: temporaryPassword || undefined,
      }),
    onSuccess: async () => {
      setEmail('')
      setFullName('')
      setTemporaryPassword('')
      setFormError(null)
      await queryClient.invalidateQueries({ queryKey: ['enterprise-members', organizationId] })
    },
    onError: (error: Error) => setFormError(error.message),
  })

  const updateMember = useMutation({
    mutationFn: (payload: { id: string; role?: string; status?: string }) =>
      updateEnterpriseMembership(organizationId, payload.id, {
        role: payload.role,
        status: payload.status,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['enterprise-members', organizationId] })
    },
  })

  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold">{tr('Članovi organizacije')}</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {tr('Uloge ostaju administrator, analitičar i pregled. Privremena lozinka se ne prikazuje ponovo.')}
        </p>
      </div>
      {!isAdmin ? (
        <p className="rounded-2xl border border-border px-4 py-3 text-sm text-muted-foreground">
          {tr('Nemate dozvolu da pregledate ili menjate članove. To može samo administrator organizacije.')}
        </p>
      ) : (
        <>
          <form
            className="grid gap-3 rounded-2xl border border-border p-4 sm:grid-cols-2"
            onSubmit={(event) => {
              event.preventDefault()
              setFormError(null)
              addMember.mutate()
            }}
          >
            <div className="space-y-1.5">
              <Label>Ime</Label>
              <Input value={fullName} onChange={(e) => setFullName(e.target.value)} required />
            </div>
            <div className="space-y-1.5">
              <Label>Email</Label>
              <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </div>
            <div className="space-y-1.5">
              <Label>Uloga</Label>
              <Select value={role} onChange={(e) => setRole(e.target.value as EnterpriseMembershipRole)}>
                <option value="enterprise_viewer">{tr("Pregled")}</option>
                <option value="enterprise_analyst">{tr("Analitičar")}</option>
                <option value="enterprise_admin">Administrator</option>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>{tr('Privremena lozinka')}</Label>
              <Input
                type="password"
                value={temporaryPassword}
                onChange={(e) => setTemporaryPassword(e.target.value)}
                placeholder="Samo za novi nalog, najmanje 8 karaktera"
                autoComplete="new-password"
              />
            </div>
            {formError ? <p className="text-sm text-danger sm:col-span-2">{formError}</p> : null}
            <div className="sm:col-span-2">
              <Button type="submit" disabled={addMember.isPending || !email.trim() || !fullName.trim()}>
                {tr('Dodaj člana')}
              </Button>
            </div>
          </form>
          {membersQuery.isLoading ? (
            <p className="text-sm text-muted-foreground">{tr('Učitavanje članova…')}</p>
          ) : membersQuery.isError ? (
            <p className="text-sm text-danger">{tr('Članovi nisu učitani.')}</p>
          ) : (
            <div className="overflow-x-auto rounded-2xl border border-border">
              <table className="w-full min-w-[40rem] text-left text-sm">
                <thead className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
                  <tr>
                    <th className="px-3 py-2 font-medium">{tr('Član')}</th>
                    <th className="px-3 py-2 font-medium">Uloga</th>
                    <th className="px-3 py-2 font-medium">Status</th>
                    <th className="px-3 py-2 font-medium">Dodat</th>
                    <th className="px-3 py-2 font-medium">Akcija</th>
                  </tr>
                </thead>
                <tbody>
                  {(membersQuery.data ?? []).map((member) => (
                    <tr key={member.id} className="border-b border-border/70 last:border-0">
                      <td className="px-3 py-2">
                        <p className="font-medium">{member.user_full_name || '—'}</p>
                        <p className="text-xs text-muted-foreground">{member.user_email}</p>
                      </td>
                      <td className="px-3 py-2">
                        <Select
                          value={member.role}
                          onChange={(e) =>
                            updateMember.mutate({ id: member.id, role: e.target.value })
                          }
                        >
                          <option value="enterprise_viewer">{tr("Pregled")}</option>
                          <option value="enterprise_analyst">{tr("Analitičar")}</option>
                          <option value="enterprise_admin">Administrator</option>
                        </Select>
                      </td>
                      <td className="px-3 py-2">
                        {tr(
                          STATUS_LABEL_KEYS[member.status as keyof typeof STATUS_LABEL_KEYS] ??
                            member.status,
                        )}
                      </td>
                      <td className="px-3 py-2">{formatDate(member.created_at)}</td>
                      <td className="px-3 py-2">
                        {member.status === 'active' ? (
                          <Button
                            type="button"
                            variant="outline"
                            onClick={() => {
                              const ok = window.confirm(
                                tr('Deaktivirati pristup za {{email}}?', {
                                  email: member.user_email ?? tr('ovog člana'),
                                }),
                              )
                              if (ok) updateMember.mutate({ id: member.id, status: 'inactive' })
                            }}
                          >
                            Deaktiviraj
                          </Button>
                        ) : (
                          <Button
                            type="button"
                            variant="outline"
                            onClick={() => updateMember.mutate({ id: member.id, status: 'active' })}
                          >
                            Aktiviraj
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {(membersQuery.data ?? []).length === 0 ? (
                <p className="px-3 py-3 text-sm text-muted-foreground">{tr('Nema članova.')}</p>
              ) : null}
            </div>
          )}
          {updateMember.isError ? (
            <p className="text-sm text-danger">
              {updateMember.error instanceof Error
                ? updateMember.error.message
                : tr('Izmena članstva nije uspela.')}
            </p>
          ) : null}
          <p className="text-xs text-muted-foreground">
            {tr(
              '{{admin}}, {{analyst}} i {{viewer}} su jedine uloge.',
              {
                admin: tr(ROLE_LABEL_KEYS.enterprise_admin),
                analyst: tr(ROLE_LABEL_KEYS.enterprise_analyst),
                viewer: tr(ROLE_LABEL_KEYS.enterprise_viewer),
              },
            )}
          </p>
        </>
      )}
    </section>
  )
}
