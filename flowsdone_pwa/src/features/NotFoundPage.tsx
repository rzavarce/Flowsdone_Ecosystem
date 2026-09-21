import { Compass } from 'lucide-react'
import { Link } from 'react-router-dom'
import { PageHeader } from '@/components/layout/PageHeader'
import { EmptyState } from '@/components/ui/EmptyState'

/** Vista para rutas inexistentes. */
export function NotFoundPage() {
  return (
    <>
      <PageHeader title="Página no encontrada" />
      <EmptyState
        icon={Compass}
        title="No encontramos lo que buscas"
        description="La dirección no existe o fue movida."
      />
      <p className="mt-4 text-center">
        <Link to="/" className="font-medium text-primary hover:underline">
          Volver al dashboard
        </Link>
      </p>
    </>
  )
}
