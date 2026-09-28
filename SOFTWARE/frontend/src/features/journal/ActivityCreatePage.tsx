import { useSearchParams } from 'react-router-dom'

import { ActivityForm } from '@/features/journal/ActivityForm'
import type { ActivityScope, ActivityStatus } from '@/shared/api/types'
import { BackLink } from '@/shared/ui/back-button'

const STATUSES: ActivityStatus[] = ['planned', 'in_progress', 'completed', 'cancelled']

export function ActivityCreatePage() {
  const [params] = useSearchParams()
  const scope = params.get('scope')
  const statusParam = params.get('status')
  const returnTo = params.get('returnTo') ?? '/journal'
  const prefill = {
    scope_type: scope === 'row' || scope === 'tree' || scope === 'parcel' ? (scope as ActivityScope) : undefined,
    parcel_id: params.get('parcelId') ?? undefined,
    row_id: params.get('rowId') ?? undefined,
    tree_id: params.get('treeId') ?? undefined,
    return_to: returnTo,
    performed_on: params.get('date') ?? undefined,
    status: statusParam && STATUSES.includes(statusParam as ActivityStatus) ? (statusParam as ActivityStatus) : undefined,
  }

  return (
    <div className="w-full space-y-6">
      <div>
        <p className="kicker">Dnevnik</p>
        <h1 className="mt-1 text-xl font-semibold sm:text-2xl">Nova aktivnost</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Zabeležite šta je urađeno ili planirajte šta treba uraditi.
        </p>
      </div>
      <div className="rounded-xl border border-border bg-card p-4 sm:p-6">
        <ActivityForm prefill={prefill} />
      </div>
      <BackLink fallback={returnTo}>Nazad</BackLink>
    </div>
  )
}
