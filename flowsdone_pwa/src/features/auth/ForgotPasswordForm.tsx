import { LoaderCircle } from 'lucide-react'
import { useId, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { AuthError } from '@/core/auth/AuthApi'
import { useAuth } from '@/core/auth/useAuth'

/**
 * "Forgot my password" form. After submitting, it always shows the same
 * success message, whether or not the account exists - the backend never
 * reveals which emails are registered, and the UI follows that same
 * principle.
 */
export function ForgotPasswordForm() {
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
      setError(err instanceof AuthError ? err.message : 'Ocurrió un error inesperado.')
    } finally {
      setPending(false)
    }
  }

  if (sent) {
    return (
      <div className="space-y-5">
        <Alert tone="success" onDismiss={() => setSent(false)}>
          Si <strong>{email.trim()}</strong> tiene una cuenta, te llegará un enlace para restablecer la contraseña.
        </Alert>
        <Link to="/login" className="block text-center text-sm font-medium text-primary-ink hover:underline">
          Volver a iniciar sesión
        </Link>
      </div>
    )
  }

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-5" aria-describedby={error ? ids.error : undefined}>
      <div className="space-y-1.5">
        <label htmlFor={ids.email} className="text-sm font-medium">
          Correo electrónico
        </label>
        <Input
          id={ids.email}
          type="email"
          autoComplete="username"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="tu@empresa.com"
        />
      </div>

      {error && (
        <p id={ids.error} role="alert" className="rounded-xl bg-danger/10 px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}

      <Button type="submit" disabled={pending || !email.trim()} className="w-full">
        {pending && <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />}
        {pending ? 'Enviando…' : 'Enviar enlace de recuperación'}
      </Button>

      <Link to="/login" className="block text-center text-sm font-medium text-primary-ink hover:underline">
        Volver a iniciar sesión
      </Link>
    </form>
  )
}
