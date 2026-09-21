import { Plus } from 'lucide-react'
import { PageHeader } from '@/components/layout/PageHeader'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { CHANNELS } from '@/mocks/data'

/** Listado de canales de mensajería y su estado de conexión (maqueta). */
export function ChannelsPage() {
  return (
    <>
      <PageHeader
        title="Canales"
        description="Conecta y monitorea los canales por los que hablan tus agentes."
        actions={
          <Button>
            <Plus className="size-4" aria-hidden="true" />
            Nuevo canal
          </Button>
        }
      />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {CHANNELS.map((channel) => (
          <Card key={channel.id} className="p-5 transition hover:border-primary/40">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="font-semibold">{channel.name}</h2>
                <p className="text-sm text-muted">{channel.description}</p>
              </div>
              <Badge tone={channel.status.tone}>{channel.status.label}</Badge>
            </div>
            <p className="mt-5 text-2xl font-bold tracking-tight">{channel.messages.toLocaleString('es')}</p>
            <p className="text-sm text-muted">mensajes este mes</p>
          </Card>
        ))}
      </div>
    </>
  )
}
