import { Outlet } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { tr } from '@/shared/i18n/i18n'
import { SectionTabs } from '@/shared/ui/section-tabs'

export function JournalSectionLayout() {
  const { i18n } = useTranslation()
  void i18n.language
  const tabs = [
    { to: '/journal', label: tr('Aktivnosti'), end: true },
    { to: '/journal/planning', label: tr('Planiranje') },
    { to: '/journal/schedule', label: tr('Raspored') },
  ]
  return (
    <div className="w-full space-y-4">
      <SectionTabs items={tabs} />
      <Outlet />
    </div>
  )
}
