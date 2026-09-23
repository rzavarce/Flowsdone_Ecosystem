import { NavLink } from 'react-router-dom'
import { cn } from '@/lib/cn'
import { useNavItems } from './useNavItems'

/** Bottom tab bar for mobile (< lg), designed for the installed PWA. */
export function MobileNav() {
  const items = useNavItems()
  return (
    <nav
      aria-label="Principal"
      className="pb-safe fixed inset-x-0 bottom-0 z-30 border-t border-border bg-surface/90 backdrop-blur lg:hidden"
    >
      <ul className="mx-auto flex max-w-lg">
        {items.map(({ to, label, icon: Icon }) => (
          <li key={to} className="flex-1">
            <NavLink
              to={to}
              className={({ isActive }) =>
                cn(
                  'flex h-16 flex-col items-center justify-center gap-1 text-[0.6875rem] font-medium transition',
                  isActive ? 'text-primary-ink' : 'text-muted',
                )
              }
            >
              <Icon className="size-5" aria-hidden="true" />
              {label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  )
}
