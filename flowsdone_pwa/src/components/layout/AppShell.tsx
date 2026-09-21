import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import { MobileNav } from './MobileNav'
import { Sidebar } from './Sidebar'
import { Topbar } from './Topbar'

/**
 * Estructura común de las vistas autenticadas: sidebar (escritorio), barra
 * superior, contenido (`<Outlet />`) y pestañas inferiores (móvil).
 */
export function AppShell() {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <div className="flex min-h-dvh">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((c) => !c)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar />
        {/* pb-24: deja libre la barra inferior en móvil. */}
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 pb-24 sm:px-6 lg:pb-8">
          <Outlet />
        </main>
      </div>
      <MobileNav />
    </div>
  )
}
