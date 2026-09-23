import { Bot, LineChart, ShieldCheck } from 'lucide-react'
import type { ReactNode } from 'react'
import { Logo } from '@/components/layout/Logo'
import { LanguageSelect } from '@/components/layout/LanguageMenu'
import { ModeToggle } from '@/components/theme/ModeToggle'
import { useTranslation } from 'react-i18next'

const HIGHLIGHTS = [
  { icon: Bot, key: 'agents' },
  { icon: LineChart, key: 'realtime' },
  { icon: ShieldCheck, key: 'access' },
] as const

/** Props for {@link AuthLayout}. */
export interface AuthLayoutProps {
  /** Screen title (e.g. "Log in", "Activate your account"). */
  title: string
  /** Short text under the title. */
  description: string
  /** The screen's form. */
  children: ReactNode
}

/**
 * Shared layout for the public authentication screens (login, account
 * activation, forgot/reset password), TailAdmin style: a centered form on
 * the left plus a brand panel with a decorative grid on the right (desktop
 * only). The panel paints with the active template's `--primary-2`.
 */
export function AuthLayout({ title, description, children }: AuthLayoutProps) {
  const { t } = useTranslation()
  return (
    <div className="grid min-h-dvh bg-surface lg:grid-cols-2">
      <main className="pt-safe pb-safe relative flex items-center justify-center px-6 py-10 sm:px-8">
        <div className="absolute top-4 right-4 flex items-center gap-2">
          <LanguageSelect />
          <ModeToggle className="lg:hidden" />
        </div>
        <div className="w-full max-w-md">
          <Logo variant="wordmark" className="mb-8 h-9 w-auto lg:hidden" />
          <h1 className="mb-2 text-3xl font-semibold sm:text-4xl">{title}</h1>
          <p className="mb-8 text-sm text-muted">{description}</p>
          {children}
        </div>
      </main>

      <aside className="relative hidden items-center justify-center overflow-hidden bg-primary-2 p-12 text-white lg:flex dark:bg-surface-muted">
        {/* Cuadrícula decorativa (esquinas), como el GridShape de TailAdmin. */}
        <span
          aria-hidden="true"
          className="pointer-events-none absolute top-0 right-0 size-[28rem] opacity-60 [mask-image:radial-gradient(circle_at_top_right,black,transparent_70%)]"
          style={GRID}
        />
        <span
          aria-hidden="true"
          className="pointer-events-none absolute bottom-0 left-0 size-[28rem] rotate-180 opacity-60 [mask-image:radial-gradient(circle_at_top_right,black,transparent_70%)]"
          style={GRID}
        />

        <div className="relative flex max-w-sm flex-col items-center text-center">
          <Logo variant="full" tone="onDark" className="h-14 w-auto" />
          <p className="mt-6 text-white/70">{t('auth.brand.tagline')}</p>
          <ul className="mt-10 space-y-4 text-left text-sm text-white/85">
            {HIGHLIGHTS.map(({ icon: Icon, key }) => (
              <li key={key} className="flex items-center gap-3">
                <span className="inline-flex size-9 shrink-0 items-center justify-center rounded-lg bg-white/10">
                  <Icon className="size-5" aria-hidden="true" />
                </span>
                {t(`auth.brand.highlights.${key}`)}
              </li>
            ))}
          </ul>
        </div>

        <div className="absolute right-6 bottom-6">
          <ModeToggle className="rounded-full bg-white/10 text-white hover:bg-white/20 hover:text-white" />
        </div>
      </aside>
    </div>
  )
}

/** Faint 40px grid lines for the brand panel's corners. */
const GRID = {
  backgroundImage:
    'linear-gradient(rgb(255 255 255 / 0.08) 1px, transparent 1px), linear-gradient(90deg, rgb(255 255 255 / 0.08) 1px, transparent 1px)',
  backgroundSize: '40px 40px',
}
