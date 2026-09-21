import { Bell, Search } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { ModeToggle } from '@/components/theme/ModeToggle'
import { can } from '@/core/auth/permissions'
import { useAuth } from '@/core/auth/useAuth'
import { Logo } from './Logo'
import { TenantSwitcher } from './TenantSwitcher'
import { UserMenu } from './UserMenu'

/**
 * Barra superior: logo (solo móvil), búsqueda (solo perfiles que operan
 * conversaciones), tenant activo, modo de color, avisos y menú de usuario.
 */
export function Topbar() {
  const { user } = useAuth()
  const canSearch = can(user, 'conversations:manage')

  return (
    <header className="pt-safe sticky top-0 z-20 border-b border-border bg-background/80 backdrop-blur">
      <div className="flex h-16 items-center gap-3 px-4 sm:px-6">
        <Logo variant="icon" className="size-9 shrink-0 lg:hidden" />

        {canSearch && (
          <div className="relative hidden max-w-md flex-1 md:block">
            <Search
              className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted"
              aria-hidden="true"
            />
            <Input type="search" aria-label="Buscar" placeholder="Buscar conversaciones, canales…" className="pl-9" />
          </div>
        )}

        <div className="ml-auto flex min-w-0 items-center gap-1">
          <TenantSwitcher />
          <ModeToggle />
          <Button variant="ghost" size="icon" aria-label="Notificaciones" className="relative">
            <Bell className="size-5" aria-hidden="true" />
            <span className="absolute top-2.5 right-2.5 size-2 rounded-full bg-primary ring-2 ring-background" />
          </Button>
          <UserMenu />
        </div>
      </div>
    </header>
  )
}
