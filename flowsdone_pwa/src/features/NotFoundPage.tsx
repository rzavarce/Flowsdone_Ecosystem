import { Compass } from 'lucide-react'
import { Link } from 'react-router-dom'
import { PageHeader } from '@/components/layout/PageHeader'
import { EmptyState } from '@/components/ui/EmptyState'

/** View for routes that don't exist. */
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
        <Link to="/dashboard" className="font-medium text-primary-ink hover:underline">
          Volver al dashboard
        </Link>
      </p>
    </>
  )
}
