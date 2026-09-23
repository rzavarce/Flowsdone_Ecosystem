import { useParams } from 'react-router-dom'
import { ActivateAccountForm } from './ActivateAccountForm'
import { AuthLayout } from './AuthLayout'

/** Pantalla pública: crear la contraseña y activar la cuenta desde el link del email. */
export function ActivateAccountPage() {
  const { token = '' } = useParams<{ token: string }>()
  return (
    <AuthLayout title="Activa tu cuenta" description="Crea una contraseña para empezar a usar Flowsdone.">
      <ActivateAccountForm token={token} />
    </AuthLayout>
  )
}
