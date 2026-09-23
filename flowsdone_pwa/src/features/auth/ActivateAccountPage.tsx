import { useParams } from 'react-router-dom'
import { ActivateAccountForm } from './ActivateAccountForm'
import { AuthLayout } from './AuthLayout'

/** Public screen: set a password and activate the account from the email link. */
export function ActivateAccountPage() {
  const { token = '' } = useParams<{ token: string }>()
  return (
    <AuthLayout title="Activa tu cuenta" description="Crea una contraseña para empezar a usar Flowsdone.">
      <ActivateAccountForm token={token} />
    </AuthLayout>
  )
}
