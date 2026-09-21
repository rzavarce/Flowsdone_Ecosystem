import { LogOut } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Avatar } from '@/components/ui/Avatar'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { ROLE_META } from '@/core/auth/permissions'
import { useAuth } from '@/core/auth/useAuth'

/** Avatar de la barra superior con desplegable: datos del usuario y cierre de sesión. */
export function UserMenu() {
  const { user, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onPointer = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', onPointer)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onPointer)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  if (!user) return null

  return (
    <div ref={ref} className="relative ml-1">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-label="Menú de usuario"
        aria-haspopup="true"
        aria-expanded={open}
        className="cursor-pointer rounded-full"
      >
        <Avatar name={user.name} />
      </button>

      {open && (
        <div className="absolute top-full right-0 z-30 mt-2 w-64 rounded-card border border-border bg-surface p-4 shadow-card">
          <p className="truncate font-semibold">{user.name}</p>
          <p className="truncate text-sm text-muted">{user.email}</p>
          <Badge tone="primary" className="mt-2">
            {ROLE_META[user.role].label}
          </Badge>
          <Button variant="secondary" size="sm" className="mt-4 w-full" onClick={() => void logout()}>
            <LogOut className="size-4" aria-hidden="true" />
            Cerrar sesión
          </Button>
        </div>
      )}
    </div>
  )
}
