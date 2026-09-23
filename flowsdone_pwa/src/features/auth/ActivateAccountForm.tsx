import { Eye, EyeOff, LoaderCircle } from 'lucide-react'
import { useId, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { AuthError } from '@/core/auth/AuthApi'
import { homePathFor } from '@/core/auth/permissions'
import { useAuth } from '@/core/auth/useAuth'
import { useTranslation } from 'react-i18next'

/** Same minimum the backend enforces (MIN_PASSWORD_LENGTH in create_user.py). */
const MIN_PASSWORD_LENGTH = 10

/** Props for {@link ActivateAccountForm}. */
export interface ActivateAccountFormProps {
  /** Activation link token, taken from the URL. */
  token: string
}

/**
 * Form to set a password and activate the account. The route has no
 * `PublicOnly` guard (see `router.tsx`: the link must work even if this
 * browser already has another session open), so this component handles the
 * post-activation redirect by hand, to the home screen of the newly
 * activated account.
 */
export function ActivateAccountForm({ token }: ActivateAccountFormProps) {
  const { t } = useTranslation()
  const { activateAccount } = useAuth()
  const navigate = useNavigate()
  const ids = { password: useId(), confirm: useId(), error: useId() }
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const mismatch = confirm.length > 0 && password !== confirm

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    if (password !== confirm) {
      setError(t('auth.passwordMismatch'))
      return
    }
    setPending(true)
    setError(null)
    try {
      const user = await activateAccount(token, password)
      navigate(homePathFor(user), { replace: true })
    } catch (err) {
      setError(err instanceof AuthError ? err.message : t('common.unexpectedError'))
      setPending(false)
    }
  }

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-5" aria-describedby={error ? ids.error : undefined}>
      <div className="space-y-1.5">
        <label htmlFor={ids.password} className="text-sm font-medium">
          {t('auth.password')}
        </label>
        <div className="relative">
          <Input
            id={ids.password}
            type={showPassword ? 'text' : 'password'}
            autoComplete="new-password"
            required
            minLength={MIN_PASSWORD_LENGTH}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="pr-11"
          />
          <button
            type="button"
            onClick={() => setShowPassword((s) => !s)}
            aria-label={showPassword ? t('auth.hidePassword') : t('auth.showPassword')}
            aria-pressed={showPassword}
            className="absolute top-1/2 right-2 inline-flex size-8 -translate-y-1/2 cursor-pointer items-center justify-center rounded-lg text-muted hover:text-foreground"
          >
            {showPassword ? <EyeOff className="size-4" aria-hidden="true" /> : <Eye className="size-4" aria-hidden="true" />}
          </button>
        </div>
        <p className="text-xs text-muted">{t('auth.minLength', { count: MIN_PASSWORD_LENGTH })}</p>
      </div>

      <div className="space-y-1.5">
        <label htmlFor={ids.confirm} className="text-sm font-medium">
          {t('auth.confirmPassword')}
        </label>
        <Input
          id={ids.confirm}
          type={showPassword ? 'text' : 'password'}
          autoComplete="new-password"
          required
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          aria-invalid={mismatch}
        />
        {mismatch && <p className="text-xs text-danger">{t('auth.passwordMismatch')}</p>}
      </div>

      {error && (
        <p id={ids.error} role="alert" className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}

      <Button
        type="submit"
        disabled={pending || password.length < MIN_PASSWORD_LENGTH || !confirm}
        className="w-full"
      >
        {pending && <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />}
        {pending ? t('auth.activate.submitting') : t('auth.activate.submit')}
      </Button>
    </form>
  )
}
