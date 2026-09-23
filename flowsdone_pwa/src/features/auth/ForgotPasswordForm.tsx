import { LoaderCircle } from 'lucide-react'
import { useId, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { AuthError } from '@/core/auth/AuthApi'
import { useAuth } from '@/core/auth/useAuth'
import { Trans, useTranslation } from 'react-i18next'

/**
 * "Forgot my password" form. After submitting, it always shows the same
 * success message, whether or not the account exists - the backend never
 * reveals which emails are registered, and the UI follows that same
 * principle.
 */
export function ForgotPasswordForm() {
  const { t } = useTranslation()
  const { requestPasswordReset } = useAuth()
  const ids = { email: useId(), error: useId() }
  const [email, setEmail] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sent, setSent] = useState(false)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setPending(true)
    setError(null)
    try {
      await requestPasswordReset(email.trim())
      setSent(true)
    } catch (err) {
      setError(err instanceof AuthError ? err.message : t('common.unexpectedError'))
    } finally {
      setPending(false)
    }
  }

  if (sent) {
    return (
      <div className="space-y-5">
        <Alert tone="success" onDismiss={() => setSent(false)}>
          <Trans i18nKey="auth.forgot.sent" values={{ email: email.trim() }} components={{ strong: <strong /> }} />
        </Alert>
        <Link to="/login" className="block text-center text-sm font-medium text-primary-ink hover:underline">
          {t('auth.backToLogin')}
        </Link>
      </div>
    )
  }

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-5" aria-describedby={error ? ids.error : undefined}>
      <div className="space-y-1.5">
        <label htmlFor={ids.email} className="text-sm font-medium">
          {t('auth.email')}
        </label>
        <Input
          id={ids.email}
          type="email"
          autoComplete="username"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder={t('auth.emailPlaceholder')}
        />
      </div>

      {error && (
        <p id={ids.error} role="alert" className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}

      <Button type="submit" disabled={pending || !email.trim()} className="w-full">
        {pending && <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />}
        {pending ? t('auth.forgot.submitting') : t('auth.forgot.submit')}
      </Button>

      <Link to="/login" className="block text-center text-sm font-medium text-primary-ink hover:underline">
        {t('auth.backToLogin')}
      </Link>
    </form>
  )
}
