import { Bell, Search } from 'lucide-react'
import { Avatar } from '@/components/ui/Avatar'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { ModeToggle } from '@/components/theme/ModeToggle'
import { Logo } from './Logo'

/** Barra superior: logo (solo móvil), búsqueda, modo de color, avisos y perfil. */
export function Topbar() {
  return (
    <header className="pt-safe sticky top-0 z-20 border-b border-border bg-background/80 backdrop-blur">
      <div className="flex h-16 items-center gap-3 px-4 sm:px-6">
        <Logo showName={false} className="lg:hidden" />

        <div className="relative max-w-md flex-1">
          <Search
            className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted"
            aria-hidden="true"
          />
          <Input type="search" aria-label="Buscar" placeholder="Buscar conversaciones, canales…" className="pl-9" />
        </div>

        <div className="ml-auto flex items-center gap-1">
          <ModeToggle />
          <Button variant="ghost" size="icon" aria-label="Notificaciones" className="relative">
            <Bell className="size-5" aria-hidden="true" />
            <span className="absolute top-2.5 right-2.5 size-2 rounded-full bg-primary ring-2 ring-background" />
          </Button>
          <Avatar name="Roger Zavarce" className="ml-1" />
        </div>
      </div>
    </header>
  )
}
