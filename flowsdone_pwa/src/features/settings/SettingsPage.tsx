import { PageHeader } from '@/components/layout/PageHeader'
import { Card, CardHeader } from '@/components/ui/Card'
import { ThemePicker } from '@/components/theme/ThemePicker'

/** Ajustes: por ahora, solo la apariencia (template y modo de color). */
export function SettingsPage() {
  return (
    <>
      <PageHeader title="Ajustes" description="Personaliza la consola a tu gusto." />
      <Card>
        <CardHeader title="Apariencia" description="El template y el modo se guardan en este dispositivo." />
        <div className="p-5">
          <ThemePicker />
        </div>
      </Card>
    </>
  )
}
