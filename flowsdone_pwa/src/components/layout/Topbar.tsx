import { Bell, Menu, Search } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { ModeToggle } from '@/components/theme/ModeToggle'
import { can } from '@/core/auth/permissions'
import { useAuth } from '@/core/auth/useAuth'
import { Logo } from './Logo'
import { TenantSwitcher } from './TenantSwitcher'
import { UserMenu } from './UserMenu'
import { useTranslation } from 'react-i18next'

/** Props for {@link Topbar}. */
export interface TopbarProps {
  /** Current sidebar state, to label the toggle. */
  sidebarCollapsed: boolean
  /** Collapses/expands the desktop sidebar. */
  onToggleSidebar: () => void
}

/** Round, bordered icon button used on the right side of the top bar (TailAdmin style). */
export const TOPBAR_ICON_BUTTON =
  'relative inline-flex size-11 shrink-0 cursor-pointer items-center justify-center rounded-full border border-border bg-chrome text-muted transition hover:bg-surface-muted hover:text-foreground'

/**
 * Top bar: sidebar toggle (desktop), logo (mobile only), search (only for
 * profiles that operate conversations, focusable with Ctrl/⌘+K), active
 * tenant, color mode, notifications and user menu.
 */
export function Topbar({ sidebarCollapsed, onToggleSidebar }: TopbarProps) {
  const { t } = useTranslation()
  const { user } = useAuth()
  const canSearch = can(user, 'conversations:manage')
  const searchRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!canSearch) return
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        searchRef.current?.focus()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [canSearch])

  return (
    <header className="pt-safe sticky top-0 z-20 border-b border-border bg-chrome">
      <div className="flex h-16 items-center gap-3 px-4 lg:h-[4.5rem] lg:gap-4 lg:px-6">
        <button
          type="button"
          onClick={onToggleSidebar}
          aria-label={sidebarCollapsed ? t('layout.expandMenu') : t('layout.collapseMenu')}
          className="hidden size-11 shrink-0 cursor-pointer items-center justify-center rounded-lg border border-border text-muted transition hover:bg-surface-muted hover:text-foreground lg:inline-flex"
        >
          <Menu className="size-5" aria-hidden="true" />
        </button>

        <Logo variant="icon" className="size-9 shrink-0 lg:hidden" />

        {canSearch && (
          <div className="relative hidden w-full max-w-[26.875rem] md:block">
            <Search
              className="pointer-events-none absolute top-1/2 left-4 size-5 -translate-y-1/2 text-muted"
              aria-hidden="true"
            />
            <input
              ref={searchRef}
              type="search"
              aria-label={t('layout.search')}
              placeholder={t('layout.searchPlaceholder')}
              className="h-11 w-full rounded-lg border border-border bg-transparent py-2.5 pr-16 pl-12 text-sm shadow-theme-xs placeholder:text-muted/70 focus-visible:border-primary/60 focus-visible:ring-3 focus-visible:ring-primary/15 focus-visible:outline-none"
            />
            <kbd
              aria-hidden="true"
              className="pointer-events-none absolute top-1/2 right-2.5 -translate-y-1/2 rounded-lg border border-border bg-background px-2 py-1 font-sans text-xs text-muted"
            >
              Ctrl K
            </kbd>
          </div>
        )}

        <div className="ml-auto flex min-w-0 items-center gap-2 sm:gap-3">
          <TenantSwitcher />
          <ModeToggle className={TOPBAR_ICON_BUTTON} />
          <button type="button" aria-label={t('layout.notifications')} className={TOPBAR_ICON_BUTTON}>
            <Bell className="size-5" aria-hidden="true" />
            <span className="absolute top-0.5 right-0 flex size-2.5">
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-orange-400 opacity-75 motion-reduce:hidden" />
              <span className="relative inline-flex size-2.5 rounded-full bg-orange-400" />
            </span>
          </button>
          <UserMenu />
        </div>
      </div>
    </header>
  )
}
