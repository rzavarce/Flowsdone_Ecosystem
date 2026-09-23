import { useParams } from 'react-router-dom'
import { ActivateAccountForm } from './ActivateAccountForm'
import { AuthLayout } from './AuthLayout'
import { useTranslation } from 'react-i18next'

/** Public screen: set a password and activate the account from the email link. */
export function ActivateAccountPage() {
  const { t } = useTranslation()
  const { token = '' } = useParams<{ token: string }>()
  return (
    <AuthLayout title={t('auth.activate.title')} description={t('auth.activate.description')}>
      <ActivateAccountForm token={token} />
    </AuthLayout>
  )
}
