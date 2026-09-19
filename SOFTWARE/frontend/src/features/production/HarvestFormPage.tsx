import { Link, useParams, useSearchParams } from 'react-router-dom'

import { HarvestForm } from '@/features/production/HarvestForm'

export function HarvestFormPage() {
  const { parcelId } = useParams()
  const [params] = useSearchParams()
  const year = Number(params.get('year') || '') || new Date().getFullYear()

  if (!parcelId) return null

  return (
    <div className="mx-auto w-full max-w-3xl space-y-6">
      <div>
        <p className="kicker">Proizvodnja</p>
        <h1 className="mt-1 text-xl font-semibold sm:text-2xl">Nova berba</h1>
        <p className="mt-2 text-sm text-muted-foreground">Zabeležite količinu i, po želji, kvalitet berbe.</p>
      </div>
      <div className="rounded-xl border border-border bg-card p-4 sm:p-6">
        <HarvestForm parcelId={parcelId} year={year} />
      </div>
      <Link to={`/orchard/${parcelId}/production?year=${year}`} className="text-sm text-muted-foreground hover:text-foreground">
        Nazad na proizvodnju
      </Link>
    </div>
  )
}
