import { useParams } from 'react-router-dom'
import { AuthLayout } from './AuthLayout'
import { ResetPasswordForm } from './ResetPasswordForm'

/** Pantalla pública: fijar la contraseña nueva desde el link del email. */
export function ResetPasswordPage() {
  const { token = '' } = useParams<{ token: string }>()
  return (
    <AuthLayout title="Crea una nueva contraseña" description="Elige una contraseña nueva para tu cuenta.">
      <ResetPasswordForm token={token} />
    </AuthLayout>
  )
}
