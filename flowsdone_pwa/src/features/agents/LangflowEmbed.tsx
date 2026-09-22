import { Bot, Building2, Maximize2, Minimize2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { Spinner } from '@/components/ui/Spinner'
import { useLangflowSession } from '@/core/admin/hooks'
import { cn } from '@/lib/cn'

/** Props de {@link LangflowEmbed}. */
export interface LangflowEmbedProps {
  /** Tenant cuyos agentes se muestran; sin él (p. ej. "Todos los tenants") se pide elegir uno. */
  tenantId?: string
  /** Nombre del tenant, para los textos. */
  tenantName?: string
}

/**
 * Editor de agentes de Langflow embebido en un iframe, ya con la sesión iniciada.
 *
 * Cada tenant tiene su propio usuario en Langflow (con una carpeta por proyecto), así
 * que al cambiar de tenant en el selector solo se ven los agentes de ese tenant. El
 * gateway prepara ese usuario y devuelve una URL de un solo uso; el navegador nunca ve
 * la contraseña de Langflow. Como el ticket se consume al cargar, el iframe se
 * monta con `key={tenantId}`: cada tenant carga con su propio ticket.
 *
 * Langflow debe poder ser enmarcado por el dominio de la PWA y compartir sitio con él
 * (subdominios hermanos), para que sus cookies de sesión viajen dentro del iframe.
 *
 * El botón de pantalla completa usa la Fullscreen API del navegador sobre el
 * contenedor (no solo el iframe) y va superpuesto en la esquina inferior
 * derecha: la superior la ocupa el botón de usuario propio de Langflow.
 *
 * Llena todo el alto disponible de la página (`h-full`): `AgentsPage` le da
 * ese alto real con un `flex-1` propio, en vez de calcularlo aquí a ojo.
 */
export function LangflowEmbed({ tenantId, tenantName }: LangflowEmbedProps) {
  const session = useLangflowSession(tenantId)
  const containerRef = useRef<HTMLDivElement>(null)
  const [isFullscreen, setIsFullscreen] = useState(false)

  useEffect(() => {
    const onChange = () => setIsFullscreen(document.fullscreenElement === containerRef.current)
    document.addEventListener('fullscreenchange', onChange)
    return () => document.removeEventListener('fullscreenchange', onChange)
  }, [])

  const toggleFullscreen = () => {
    if (document.fullscreenElement) {
      void document.exitFullscreen()
    } else {
      void containerRef.current?.requestFullscreen()
    }
  }

  if (!tenantId) {
    return (
      <EmptyState
        icon={Building2}
        title="Elige un tenant"
        description="Cada tenant tiene su propio espacio en Langflow. Selecciona uno en la barra superior para ver y editar sus agentes."
      />
    )
  }
  if (session.isPending) return <Spinner label={`Abriendo Langflow de ${tenantName ?? 'este tenant'}`} className="py-20" />
  if (session.isError) {
    return (
      <Alert tone="danger">
        <p>No se pudo abrir Langflow: {session.error.message}</p>
        <Button variant="secondary" size="sm" className="mt-3" onClick={() => void session.refetch()}>
          Reintentar
        </Button>
      </Alert>
    )
  }
  if (!session.data.url) {
    return (
      <Card className="flex h-full min-h-80 flex-col items-center justify-center border-dashed p-6 text-center">
        <span className="mb-4 inline-flex size-14 items-center justify-center rounded-2xl bg-accent text-primary-ink">
          <Bot className="size-7" aria-hidden="true" />
        </span>
        <h2 className="text-lg font-semibold">Aquí se embeberá Langflow</h2>
        <p className="mt-1 max-w-md text-sm text-muted">Modo maqueta: no hay un Langflow real conectado.</p>
      </Card>
    )
  }
  return (
    <div ref={containerRef} className={cn('relative h-full min-h-80', isFullscreen && 'bg-background p-2')}>
      <Button
        variant="secondary"
        size="icon"
        aria-label={isFullscreen ? 'Salir de pantalla completa' : 'Ver a pantalla completa'}
        title={isFullscreen ? 'Salir de pantalla completa' : 'Ver a pantalla completa'}
        onClick={toggleFullscreen}
        className="absolute bottom-3 right-3 z-10"
      >
        {isFullscreen ? <Minimize2 className="size-4" aria-hidden="true" /> : <Maximize2 className="size-4" aria-hidden="true" />}
      </Button>
      <iframe
        key={tenantId}
        title="Editor de agentes (Langflow)"
        src={session.data.url}
        // scripts + same-origin son necesarios para que Langflow funcione; el resto
        // se limita a lo que usa (formularios, descargas, ventanas de auth).
        sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-downloads"
        className="h-full w-full rounded-card border border-border bg-surface"
      />
    </div>
  )
}
