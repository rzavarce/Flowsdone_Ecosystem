import { AuthLayout } from './AuthLayout'
import { LoginForm } from './LoginForm'

/** Pantalla pública de acceso: panel de marca (solo escritorio) + formulario. */
export function LoginPage() {
  return (
    <AuthLayout title="Inicia sesión" description="Ingresa con tu cuenta de Flowsdone.">
      <LoginForm />
    </AuthLayout>
  )
}
