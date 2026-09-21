import { Bot } from 'lucide-react'
import { Card } from '@/components/ui/Card'

/** Props de {@link LangflowEmbed}. */
export interface LangflowEmbedProps {
  /** URL de Langflow; si falta se muestra la maqueta del lienzo. */
  url?: string
}

/**
 * Editor de agentes de Langflow embebido en un iframe.
 *
 * Para que el navegador lo muestre, Langflow debe permitir ser enmarcado por
 * el dominio de la PWA (`frame-ancestors`) y compartir sesión con ella; eso
 * se resuelve junto con el backend de autenticación.
 */
export function LangflowEmbed({ url }: LangflowEmbedProps) {
  if (!url) {
    return (
      <Card className="flex h-[calc(100dvh-16rem)] min-h-80 flex-col items-center justify-center border-dashed p-6 text-center">
        <span className="mb-4 inline-flex size-14 items-center justify-center rounded-2xl bg-accent text-primary-ink">
          <Bot className="size-7" aria-hidden="true" />
        </span>
        <h2 className="text-lg font-semibold">Aquí se embeberá Langflow</h2>
        <p className="mt-1 max-w-md text-sm text-muted">
          Define <code className="rounded bg-surface-muted px-1.5 py-0.5">VITE_LANGFLOW_URL</code> para cargar el editor de flujos en este panel.
        </p>
      </Card>
    )
  }
  return (
    <iframe
      title="Editor de agentes (Langflow)"
      src={url}
      // scripts + same-origin son necesarios para que Langflow funcione; el resto
      // se limita a lo que usa (formularios, descargas, ventanas de auth).
      sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-downloads"
      className="h-[calc(100dvh-16rem)] min-h-80 w-full rounded-card border border-border bg-surface"
    />
  )
}
