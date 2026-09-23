import { AuthLayout } from './AuthLayout'
import { ForgotPasswordForm } from './ForgotPasswordForm'

/** Pantalla pública: pedir el enlace de recuperación de contraseña. */
export function ForgotPasswordPage() {
  return (
    <AuthLayout title="Recupera tu contraseña" description="Te enviaremos un enlace para crear una nueva.">
      <ForgotPasswordForm />
    </AuthLayout>
  )
}
