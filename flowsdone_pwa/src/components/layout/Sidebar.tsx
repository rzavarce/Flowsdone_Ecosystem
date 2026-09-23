import { NavLink } from 'react-router-dom'
import { cn } from '@/lib/cn'
import { Logo } from './Logo'
import { useNavItems } from './useNavItems'
import { useTranslation } from 'react-i18next'

/** Props for {@link Sidebar}. */
export interface SidebarProps {
  /** Icons-only mode; toggled from the top bar. */
  collapsed: boolean
}

/** Desktop side navigation (>= lg), TailAdmin style; collapsible down to icons only. */
export function Sidebar({ collapsed }: SidebarProps) {
  const { t } = useTranslation()
  const items = useNavItems()
  return (
    <aside
      className={cn(
        'sticky top-0 hidden h-dvh shrink-0 flex-col border-r border-border bg-chrome px-5 transition-[width] duration-300 ease-in-out lg:flex',
        collapsed ? 'w-[5.625rem]' : 'w-[18.125rem]',
      )}
    >
      <div className={cn('flex py-8', collapsed && 'justify-center')}>
        <Logo variant={collapsed ? 'icon' : 'wordmark'} className={collapsed ? 'size-9' : 'h-9 w-auto'} />
      </div>

      <nav aria-label={t('layout.mainNav')} className="no-scrollbar flex-1 overflow-y-auto pb-6">
        {/* Rótulo visual: la <nav> ya tiene nombre accesible, así que no es un heading. */}
        <p
          aria-hidden="true"
          className={cn(
            'mb-4 flex text-xs leading-5 tracking-wide text-muted/80 uppercase',
            collapsed && 'justify-center',
          )}
        >
          {collapsed ? '···' : t('layout.menu')}
        </p>
        <ul className="flex flex-col gap-1">
          {items.map(({ to, label, icon: Icon }) => (
            <li key={to}>
              <NavLink
                to={to}
                title={collapsed ? label : undefined}
                className={({ isActive }) =>
                  cn(
                    'group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition',
                    collapsed && 'justify-center',
                    isActive
                      ? 'bg-primary/10 text-primary-ink dark:bg-primary/15'
                      : 'text-foreground/80 hover:bg-surface-muted hover:text-foreground',
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon
                      className={cn(
                        'size-6 shrink-0',
                        isActive ? 'text-primary-ink' : 'text-muted group-hover:text-foreground/80',
                      )}
                      strokeWidth={1.75}
                      aria-hidden="true"
                    />
                    <span className={cn(collapsed && 'sr-only')}>{label}</span>
                  </>
                )}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </aside>
  )
}
