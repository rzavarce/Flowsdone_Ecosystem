import { AuthLayout } from './AuthLayout'
import { ForgotPasswordForm } from './ForgotPasswordForm'
import { useTranslation } from 'react-i18next'

/** Public screen: request the password reset link. */
export function ForgotPasswordPage() {
  const { t } = useTranslation()
  return (
    <AuthLayout title={t('auth.forgot.title')} description={t('auth.forgot.description')}>
      <ForgotPasswordForm />
    </AuthLayout>
  )
}
