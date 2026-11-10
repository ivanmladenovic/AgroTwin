import { Outlet } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { tr } from '@/shared/i18n/i18n'
import { SectionTabs } from '@/shared/ui/section-tabs'

export function CostsSectionLayout() {
  const { i18n } = useTranslation()
  void i18n.language
  const tabs = [
    { to: '/costs', label: tr('Troškovi'), end: true },
    { to: '/costs/workforce', label: tr('Radna snaga') },
    { to: '/costs/invoices', label: tr('Računi') },
  ]
  return (
    <div className="w-full space-y-4">
      <SectionTabs items={tabs} />
      <Outlet />
    </div>
  )
}
