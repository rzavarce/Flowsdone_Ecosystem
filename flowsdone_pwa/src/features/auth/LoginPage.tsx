import { Bot, LineChart, ShieldCheck } from 'lucide-react'
import { Logo } from '@/components/layout/Logo'
import { ModeToggle } from '@/components/theme/ModeToggle'
import { LoginForm } from './LoginForm'

const HIGHLIGHTS = [
  { icon: Bot, text: 'Agentes de IA conectados a todos tus canales.' },
  { icon: LineChart, text: 'Indicadores y conversaciones en tiempo real.' },
  { icon: ShieldCheck, text: 'Acceso segmentado por perfil y por tenant.' },
]

/** Pantalla pública de acceso: panel de marca (solo escritorio) + formulario. */
export function LoginPage() {
  return (
    <div className="grid min-h-dvh lg:grid-cols-2">
      <aside
        className="relative hidden flex-col justify-between overflow-hidden p-12 text-[#F2FBF7] lg:flex"
        style={{ backgroundImage: 'linear-gradient(160deg, #04141f 0%, #04141f 35%, var(--primary-2) 140%)' }}
      >
        <Logo variant="full" tone="onDark" className="h-14 w-auto self-start" />

        <div>
          <h2 className="max-w-md text-4xl font-bold tracking-tight">Tu plataforma de IA generativa, en un solo lugar.</h2>
          <ul className="mt-8 space-y-4">
            {HIGHLIGHTS.map(({ icon: Icon, text }) => (
              <li key={text} className="flex items-center gap-3">
                <span className="inline-flex size-9 shrink-0 items-center justify-center rounded-xl bg-white/10 text-[#19B4E6]">
                  <Icon className="size-5" aria-hidden="true" />
                </span>
                {text}
              </li>
            ))}
          </ul>
        </div>

        <p className="text-sm opacity-70">© Flowsdone</p>
        {/* Halos decorativos en los colores de la marca */}
        <span className="pointer-events-none absolute -right-24 -bottom-24 size-96 rounded-full bg-[#19B4E6]/15 blur-2xl" aria-hidden="true" />
        <span className="pointer-events-none absolute -top-24 right-16 size-64 rounded-full bg-[#3EFF8B]/10 blur-3xl" aria-hidden="true" />
      </aside>

      <main className="pt-safe pb-safe relative flex items-center justify-center px-4 py-10 sm:px-8">
        <div className="absolute top-4 right-4">
          <ModeToggle />
        </div>
        <div className="w-full max-w-md">
          <Logo variant="wordmark" className="mb-8 h-9 w-auto lg:hidden" />
          <h1 className="text-3xl font-bold tracking-tight">Inicia sesión</h1>
          <p className="mt-1 mb-8 text-muted">Ingresa con tu cuenta de Flowsdone.</p>
          <LoginForm />
        </div>
      </main>
    </div>
  )
}
