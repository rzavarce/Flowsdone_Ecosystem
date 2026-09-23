import { PageHeader } from '@/components/layout/PageHeader'
import { Card, CardHeader } from '@/components/ui/Card'
import { ThemePicker } from '@/components/theme/ThemePicker'
import { can } from '@/core/auth/permissions'
import { useAuth } from '@/core/auth/useAuth'
import { PlatformIntegrations } from './PlatformIntegrations'
import { useTranslation } from 'react-i18next'

/** Settings: appearance (everyone) and platform integrations (admin only). */
export function SettingsPage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  return (
    <>
      <PageHeader title={t('nav.settings')} description={t('settings.description')} />
      <Card>
        <CardHeader title={t('settings.appearance.title')} description={t('settings.appearance.description')} />
        <div className="p-5">
          <ThemePicker />
        </div>
      </Card>
      {can(user, 'platform:manage') && (
        <div className="mt-6">
          <PlatformIntegrations />
        </div>
      )}
    </>
  )
}
