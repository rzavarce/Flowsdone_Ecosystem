import { PanelLeftClose, PanelLeftOpen } from 'lucide-react'
import { NavLink } from 'react-router-dom'
import { Button } from '@/components/ui/Button'
import { cn } from '@/lib/cn'
import { Logo } from './Logo'
import { useNavItems } from './useNavItems'

/** Props de {@link Sidebar}. */
export interface SidebarProps {
  collapsed: boolean
  onToggle: () => void
}

/** Navegación lateral de escritorio (>= lg); colapsable a solo iconos. */
export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const items = useNavItems()
  return (
    <aside
      className={cn(
        'sticky top-0 hidden h-dvh shrink-0 flex-col border-r border-border bg-surface transition-[width] duration-200 lg:flex',
        collapsed ? 'w-[4.5rem]' : 'w-64',
      )}
    >
      <div className={cn('flex h-16 items-center px-4', collapsed && 'justify-center')}>
        <Logo variant={collapsed ? 'icon' : 'wordmark'} className={collapsed ? 'size-9' : 'h-8 w-auto'} />
      </div>

      <nav aria-label="Principal" className="flex-1 space-y-1 px-3 py-2">
        {items.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            title={collapsed ? label : undefined}
            className={({ isActive }) =>
              cn(
                'flex h-11 items-center gap-3 rounded-xl px-3 text-sm font-medium transition',
                collapsed && 'justify-center px-0',
                isActive ? 'bg-accent text-primary-ink' : 'text-muted hover:bg-surface-muted hover:text-foreground',
              )
            }
          >
            <Icon className="size-5 shrink-0" aria-hidden="true" />
            <span className={cn(collapsed && 'sr-only')}>{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className={cn('p-3', collapsed && 'flex justify-center')}>
        <Button
          variant="ghost"
          size={collapsed ? 'icon' : 'md'}
          onClick={onToggle}
          aria-label={collapsed ? 'Expandir menú' : 'Contraer menú'}
          className={cn(!collapsed && 'w-full justify-start')}
        >
          {collapsed ? (
            <PanelLeftOpen className="size-5" aria-hidden="true" />
          ) : (
            <>
              <PanelLeftClose className="size-5" aria-hidden="true" />
              Contraer
            </>
          )}
        </Button>
      </div>
    </aside>
  )
}
