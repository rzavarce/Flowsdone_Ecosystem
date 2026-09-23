import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import { MobileNav } from './MobileNav'
import { Sidebar } from './Sidebar'
import { Topbar } from './Topbar'

/**
 * Common shell for authenticated views: sidebar (desktop), top bar (which
 * also holds the sidebar collapse toggle), content (`<Outlet />`) and bottom
 * tabs (mobile).
 */
export function AppShell() {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <div className="flex min-h-dvh">
      <Sidebar collapsed={collapsed} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar sidebarCollapsed={collapsed} onToggleSidebar={() => setCollapsed((c) => !c)} />
        {/* pb-24: deja libre la barra inferior en móvil. */}
        <main className="w-full flex-1 p-4 pb-24 md:p-6 lg:pb-6">
          <Outlet />
        </main>
      </div>
      <MobileNav />
    </div>
  )
}
