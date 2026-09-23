import { AuthLayout } from './AuthLayout'
import { LoginForm } from './LoginForm'
import { useTranslation } from 'react-i18next'

/** Public login screen: brand panel (desktop only) + form. */
export function LoginPage() {
  const { t } = useTranslation()
  return (
    <AuthLayout title={t('auth.login.title')} description={t('auth.login.description')}>
      <LoginForm />
    </AuthLayout>
  )
}
