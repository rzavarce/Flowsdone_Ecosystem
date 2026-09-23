import { PageHeader } from '@/components/layout/PageHeader'
import { Card, CardHeader } from '@/components/ui/Card'
import { ThemePicker } from '@/components/theme/ThemePicker'
import { can } from '@/core/auth/permissions'
import { useAuth } from '@/core/auth/useAuth'
import { PlatformIntegrations } from './PlatformIntegrations'

/** Settings: appearance (everyone) and platform integrations (admin only). */
export function SettingsPage() {
  const { user } = useAuth()
  return (
    <>
      <PageHeader title="Ajustes" description="Personaliza la consola a tu gusto." />
      <Card>
        <CardHeader title="Apariencia" description="El template y el modo se guardan en este dispositivo." />
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
