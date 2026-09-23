import { Bell, Menu } from 'lucide-react'
import { ModeToggle } from '@/components/theme/ModeToggle'
import { GlobalSearch } from './GlobalSearch'
import { Logo } from './Logo'
import { TenantSwitcher } from './TenantSwitcher'
import { UserMenu } from './UserMenu'
import { useCanSearch } from './useSearchScope'
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
 * Top bar: sidebar toggle (desktop), logo (mobile only), global search
 * (for profiles with something to search, focusable with Ctrl/⌘+K), active
 * tenant, color mode, notifications and user menu.
 */
export function Topbar({ sidebarCollapsed, onToggleSidebar }: TopbarProps) {
  const { t } = useTranslation()
  const canSearch = useCanSearch()

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

        {canSearch && <GlobalSearch />}

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
