import { useParams, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { HarvestForm } from '@/features/production/HarvestForm'
import { BackLink } from '@/shared/ui/back-button'
import { tr } from '@/shared/i18n/i18n'

export function HarvestFormPage() {
  const { i18n } = useTranslation()
  void i18n.language
  const { parcelId } = useParams()
  const [params] = useSearchParams()
  const year = Number(params.get('year') || '') || new Date().getFullYear()
  const backHref = `/orchard/${parcelId}/production?year=${year}`

  if (!parcelId) return null

  return (
    <div className="w-full space-y-6">
      <div>
        <p className="kicker">{tr('Proizvodnja')}</p>
        <h1 className="mt-1 text-xl font-semibold sm:text-2xl">{tr('Nova berba')}</h1>
        <p className="mt-2 text-sm text-muted-foreground">{tr('Zabeležite količinu i, po želji, kvalitet berbe.')}</p>
      </div>
      <div className="rounded-xl border border-border bg-card p-4 sm:p-6">
        <HarvestForm parcelId={parcelId} year={year} />
      </div>
      <BackLink fallback={backHref}>{tr('Nazad na proizvodnju')}</BackLink>
    </div>
  )
}
