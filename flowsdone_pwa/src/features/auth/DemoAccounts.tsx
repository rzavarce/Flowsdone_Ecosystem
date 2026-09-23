import { DEMO_ACCOUNTS } from '@/core/auth/mockAuthApi'
import { ROLE_META } from '@/core/auth/permissions'
import type { Credentials } from '@/core/auth/types'
import { useTranslation } from 'react-i18next'

/** Props for {@link DemoAccounts}. */
export interface DemoAccountsProps {
  onPick: (credentials: Credentials) => void
}

/** Shortcuts to fill the login form with an account of each role (mock mode only). */
export function DemoAccounts({ onPick }: DemoAccountsProps) {
  const { t } = useTranslation()
  return (
    <section aria-labelledby="demo-title" className="mt-8 rounded-xl border border-dashed border-border p-4">
      <h2 id="demo-title" className="text-sm font-semibold">
        {t('auth.demo.title')}
      </h2>
      <p className="mt-0.5 text-xs text-muted">{t('auth.demo.description')}</p>
      <ul className="mt-3 grid gap-2 sm:grid-cols-2">
        {DEMO_ACCOUNTS.map((account) => (
          <li key={account.email}>
            <button
              type="button"
              onClick={() => onPick({ email: account.email, password: account.password })}
              className="w-full cursor-pointer rounded-lg border border-border bg-surface px-3 py-2 text-left transition hover:border-primary/50 hover:bg-accent"
            >
              <span className="block text-sm font-medium">{ROLE_META[account.role].label}</span>
              <span className="block truncate text-xs text-muted">{account.email}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}
