import { Outlet } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { tr } from '@/shared/i18n/i18n'
import { SectionTabs } from '@/shared/ui/section-tabs'

export function ReportsSectionLayout() {
  const { i18n } = useTranslation()
  void i18n.language
  const tabs = [
    { to: '/reports', label: tr('Godišnji izveštaj'), end: true },
    { to: '/reports/compliance', label: tr('Usaglašenost') },
  ]
  return (
    <div className="w-full space-y-4">
      <SectionTabs items={tabs} />
      <Outlet />
    </div>
  )
}
