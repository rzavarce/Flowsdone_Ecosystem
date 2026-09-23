import { useParams } from 'react-router-dom'
import { AuthLayout } from './AuthLayout'
import { ResetPasswordForm } from './ResetPasswordForm'
import { useTranslation } from 'react-i18next'

/** Public screen: set the new password from the email link. */
export function ResetPasswordPage() {
  const { t } = useTranslation()
  const { token = '' } = useParams<{ token: string }>()
  return (
    <AuthLayout title={t('auth.reset.title')} description={t('auth.reset.description')}>
      <ResetPasswordForm token={token} />
    </AuthLayout>
  )
}
