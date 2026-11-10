import { createContext, useContext, useMemo, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { Navigate, useParams } from 'react-router-dom'

import { getEnterpriseMe, getEnterpriseOrganization } from '@/features/enterprise/api'
import type { EnterpriseMembership, EnterpriseOrganization } from '@/shared/api/types'
import { tr } from '@/shared/i18n/i18n'

type EnterpriseContextValue = {
  organizationId: string
  organization: EnterpriseOrganization | undefined
  membership: EnterpriseMembership | undefined
  memberships: EnterpriseMembership[]
  mustChangePassword: boolean
  isAdmin: boolean
  canWritePlans: boolean
}

const EnterpriseContext = createContext<EnterpriseContextValue | null>(null)

export function EnterpriseProvider({ children }: { children: ReactNode }) {
  useTranslation()
  const { organizationId = '' } = useParams()
  const meQuery = useQuery({ queryKey: ['enterprise-me'], queryFn: getEnterpriseMe })
  const mustChangePassword = Boolean(meQuery.data?.must_change_password)
  const orgQuery = useQuery({
    queryKey: ['enterprise-org', organizationId],
    queryFn: () => getEnterpriseOrganization(organizationId),
    enabled: Boolean(organizationId) && meQuery.isSuccess && !mustChangePassword,
  })

  const memberships = meQuery.data?.memberships ?? []
  const membership = memberships.find((item) => item.organization_id === organizationId)

  const value = useMemo<EnterpriseContextValue>(
    () => ({
      organizationId,
      organization: orgQuery.data,
      membership,
      memberships,
      mustChangePassword: Boolean(meQuery.data?.must_change_password),
      isAdmin: membership?.role === 'enterprise_admin',
      canWritePlans:
        membership?.role === 'enterprise_admin' || membership?.role === 'enterprise_analyst',
    }),
    [organizationId, orgQuery.data, membership, memberships, meQuery.data?.must_change_password],
  )

  if (meQuery.isLoading) {
    return <p className="p-6 text-sm text-muted-foreground">{tr('Učitavanje Enterprise naloga…')}</p>
  }
  if (mustChangePassword) {
    return <Navigate to="/enterprise/change-password" replace />
  }
  if (meQuery.isError || memberships.length === 0) {
    return <Navigate to="/" replace />
  }
  if (organizationId && !membership) {
    return <Navigate to={`/enterprise/${memberships[0]!.organization_id}`} replace />
  }
  return <EnterpriseContext.Provider value={value}>{children}</EnterpriseContext.Provider>
}

export function useEnterprise() {
  const ctx = useContext(EnterpriseContext)
  if (!ctx) throw new Error('useEnterprise mora biti unutar EnterpriseProvider')
  return ctx
}
