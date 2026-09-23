import { Eye, EyeOff, LoaderCircle } from 'lucide-react'
import { useId, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { AuthError } from '@/core/auth/AuthApi'
import { AUTH_MODE } from '@/core/auth/createAuthApi'
import { useAuth } from '@/core/auth/useAuth'
import { DemoAccounts } from './DemoAccounts'

/**
 * Login form. Once authenticated, `PublicOnly` (which wraps the route)
 * handles the redirect; this component only manages submission and errors.
 */
export function LoginForm() {
  const { login } = useAuth()
  const ids = { email: useId(), password: useId(), error: useId() }
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setPending(true)
    setError(null)
    try {
      await login({ email: email.trim(), password })
    } catch (err) {
      setError(err instanceof AuthError ? err.message : 'Ocurrió un error inesperado.')
      setPending(false)
    }
  }

  return (
    <>
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

        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <label htmlFor={ids.password} className="text-sm font-medium">
              Contraseña
            </label>
            <Link to="/forgot-password" className="text-sm font-medium text-primary-ink hover:underline">
              ¿Olvidaste tu contraseña?
            </Link>
          </div>
          <div className="relative">
            <Input
              id={ids.password}
              type={showPassword ? 'text' : 'password'}
              autoComplete="current-password"
              required
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
        </div>

        {error && (
          <p id={ids.error} role="alert" className="rounded-xl bg-danger/10 px-3 py-2 text-sm text-danger">
            {error}
          </p>
        )}

        <Button type="submit" disabled={pending || !email.trim() || !password} className="w-full">
          {pending && <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />}
          {pending ? 'Ingresando…' : 'Ingresar'}
        </Button>
      </form>

      {AUTH_MODE === 'mock' && (
        <DemoAccounts
          onPick={(c) => {
            setEmail(c.email)
            setPassword(c.password)
            setError(null)
          }}
        />
      )}
    </>
  )
}
