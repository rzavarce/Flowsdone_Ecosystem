import { Eye, EyeOff, LoaderCircle } from 'lucide-react'
import { useId, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { AuthError } from '@/core/auth/AuthApi'
import { homePathFor } from '@/core/auth/permissions'
import { useAuth } from '@/core/auth/useAuth'

/** Same minimum the backend enforces (MIN_PASSWORD_LENGTH in create_user.py). */
const MIN_PASSWORD_LENGTH = 10

/** Props for {@link ResetPasswordForm}. */
export interface ResetPasswordFormProps {
  /** Password reset link token, taken from the URL. */
  token: string
}

/**
 * Form to set the new password. The route has no `PublicOnly` guard (see
 * `router.tsx`), so this component handles the post-success redirect by
 * hand, same as `ActivateAccountForm`.
 */
export function ResetPasswordForm({ token }: ResetPasswordFormProps) {
  const { resetPassword } = useAuth()
  const navigate = useNavigate()
  const ids = { password: useId(), confirm: useId(), error: useId() }
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<{ message: string; invalidToken: boolean } | null>(null)

  const mismatch = confirm.length > 0 && password !== confirm

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    if (password !== confirm) {
      setError({ message: 'Las contraseñas no coinciden.', invalidToken: false })
      return
    }
    setPending(true)
    setError(null)
    try {
      const user = await resetPassword(token, password)
      navigate(homePathFor(user), { replace: true })
    } catch (err) {
      if (err instanceof AuthError) {
        setError({ message: err.message, invalidToken: err.code === 'invalid_token' })
      } else {
        setError({ message: 'Ocurrió un error inesperado.', invalidToken: false })
      }
      setPending(false)
    }
  }

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-5" aria-describedby={error ? ids.error : undefined}>
      <div className="space-y-1.5">
        <label htmlFor={ids.password} className="text-sm font-medium">
          Contraseña nueva
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
            aria-label={showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'}
            aria-pressed={showPassword}
            className="absolute top-1/2 right-2 inline-flex size-8 -translate-y-1/2 cursor-pointer items-center justify-center rounded-lg text-muted hover:text-foreground"
          >
            {showPassword ? <EyeOff className="size-4" aria-hidden="true" /> : <Eye className="size-4" aria-hidden="true" />}
          </button>
        </div>
        <p className="text-xs text-muted">Mínimo {MIN_PASSWORD_LENGTH} caracteres.</p>
      </div>

      <div className="space-y-1.5">
        <label htmlFor={ids.confirm} className="text-sm font-medium">
          Confirma la contraseña
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
        {mismatch && <p className="text-xs text-danger">Las contraseñas no coinciden.</p>}
      </div>

      {error && (
        <p id={ids.error} role="alert" className="rounded-xl bg-danger/10 px-3 py-2 text-sm text-danger">
          {error.message}{' '}
          {error.invalidToken && (
            <Link to="/forgot-password" className="font-medium underline">
              Pide un enlace nuevo
            </Link>
          )}
        </p>
      )}

      <Button
        type="submit"
        disabled={pending || password.length < MIN_PASSWORD_LENGTH || !confirm}
        className="w-full"
      >
        {pending && <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />}
        {pending ? 'Guardando…' : 'Guardar contraseña'}
      </Button>
    </form>
  )
}
