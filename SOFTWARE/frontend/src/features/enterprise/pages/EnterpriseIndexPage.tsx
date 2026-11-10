import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { Navigate } from 'react-router-dom'

import { getEnterpriseMe } from '@/features/enterprise/api'
import { tr } from '@/shared/i18n/i18n'

export function EnterpriseIndexPage() {
  useTranslation()
  const meQuery = useQuery({ queryKey: ['enterprise-me'], queryFn: getEnterpriseMe })

  if (meQuery.isLoading) {
    return <p className="p-6 text-sm text-muted-foreground">{tr('Učitavanje Enterprise naloga…')}</p>
  }
  if (meQuery.data?.must_change_password) {
    return <Navigate to="/enterprise/change-password" replace />
  }
  const orgId = meQuery.data?.memberships[0]?.organization_id
  if (!orgId) {
    return (
      <div className="p-6">
        <p className="text-sm text-muted-foreground">
          {tr(
            'Nalog nema aktivno Enterprise članstvo. Prijavite se kao proizvođač ili kontaktirajte administratora.',
          )}
        </p>
      </div>
    )
  }
  return <Navigate to={`/enterprise/${orgId}`} replace />
}
