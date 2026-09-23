import { AuthLayout } from './AuthLayout'
import { LoginForm } from './LoginForm'

/** Public login screen: brand panel (desktop only) + form. */
export function LoginPage() {
  return (
    <AuthLayout title="Inicia sesión" description="Ingresa con tu cuenta de Flowsdone.">
      <LoginForm />
    </AuthLayout>
  )
}
