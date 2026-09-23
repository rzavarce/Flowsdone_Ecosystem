import { ShieldAlert } from 'lucide-react'
import { Link } from 'react-router-dom'
import { PageHeader } from '@/components/layout/PageHeader'
import { EmptyState } from '@/components/ui/EmptyState'
import { homePathFor } from '@/core/auth/permissions'
import { useAuth } from '@/core/auth/useAuth'

/** 403 view: the user is authenticated but their role doesn't include this section. */
export function ForbiddenPage() {
  const { user } = useAuth()
  return (
    <>
      <PageHeader title="Sin acceso" />
      <EmptyState
        icon={ShieldAlert}
        title="Tu perfil no incluye esta sección"
        description="Si crees que deberías tener acceso, pídeselo a un administrador."
      />
      <p className="mt-4 text-center">
        <Link to={user ? homePathFor(user) : '/login'} className="font-medium text-primary-ink hover:underline">
          Ir a mi página de inicio
        </Link>
      </p>
    </>
  )
}
