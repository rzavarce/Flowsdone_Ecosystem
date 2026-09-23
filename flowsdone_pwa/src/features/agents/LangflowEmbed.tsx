import { Bot, Building2, Maximize2, Minimize2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { Spinner } from '@/components/ui/Spinner'
import { useLangflowSession } from '@/core/admin/hooks'
import { cn } from '@/lib/cn'

/** Props for {@link LangflowEmbed}. */
export interface LangflowEmbedProps {
  /** Tenant whose agents are shown; without it (e.g. "All tenants") the user is asked to pick one. */
  tenantId?: string
  /** Tenant name, for display text. */
  tenantName?: string
}

/**
 * Langflow agent editor embedded in an iframe, with the session already established.
 *
 * Each tenant has its own Langflow user (with a folder per project), so switching
 * tenants in the selector only shows that tenant's agents. The gateway provisions
 * that user and returns a single-use URL; the browser never sees the Langflow
 * password. Since the ticket is consumed on load, the iframe is mounted with
 * `key={tenantId}`: each tenant loads with its own ticket.
 *
 * Langflow must be frameable from the PWA's domain and share a site with it
 * (sibling subdomains), so its session cookies travel inside the iframe.
 *
 * The fullscreen button uses the browser's Fullscreen API on the container
 * (not just the iframe) and is overlaid in the bottom-right corner: the top
 * corner is taken by Langflow's own user button.
 *
 * Fills the page's full available height (`h-full`): `AgentsPage` gives it
 * that real height via its own `flex-1`, rather than this component
 * estimating it.
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
