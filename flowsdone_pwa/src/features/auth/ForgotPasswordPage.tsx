import { AuthLayout } from './AuthLayout'
import { ForgotPasswordForm } from './ForgotPasswordForm'

/** Public screen: request the password reset link. */
export function ForgotPasswordPage() {
  return (
    <AuthLayout title="Recupera tu contraseña" description="Te enviaremos un enlace para crear una nueva.">
      <ForgotPasswordForm />
    </AuthLayout>
  )
}
