import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { createMockAdminApi } from '@/core/admin/mockAdminApi'
import { SEED } from '@/test/adminFixtures'
import { fakeAuthApi, makeUser, renderApp } from '@/test/renderApp'
import type { Role } from '@/core/auth/types'

const h1 = (name: string | RegExp) => screen.findByRole('heading', { level: 1, name })
const navLinks = () => {
  const [sidebar] = screen.getAllByRole('navigation', { name: 'Principal' })
  return within(sidebar!)
    .getAllByRole('link')
    .map((a) => a.textContent)
}

describe('sin sesión', () => {
  it.each(['/', '/dashboard', '/channels', '/agents', '/settings'])('%s redirige a /login', async (path) => {
    renderApp(path, fakeAuthApi(null))
    expect(await h1('Inicia sesión')).toBeInTheDocument()
  })
})

describe('menú y acceso por perfil', () => {
  it.each<[Role, string[]]>([
    ['admin', ['Dashboard', 'Tenants', 'Conversaciones', 'Agentes', 'Canales', 'Usuarios', 'Planes', 'Ajustes']],
    ['tenant_manager', ['Dashboard', 'Tenants', 'Conversaciones', 'Agentes', 'Canales', 'Ajustes']],
    ['botmaster', ['Conversaciones', 'Agentes', 'Canales', 'Ajustes']],
    ['client', ['Dashboard', 'Mi empresa', 'Ajustes']],
    ['consultant', ['Dashboard', 'Ajustes']],
  ])('%s ve el menú esperado', async (role, expected) => {
    renderApp('/dashboard', fakeAuthApi(makeUser(role)))
    await screen.findAllByRole('navigation', { name: 'Principal' })
    expect(navLinks()).toEqual(expected)
    // La barra móvil comparte los mismos ítems.
    const mobile = screen.getAllByRole('navigation', { name: 'Principal' })[1]!
    expect(within(mobile).getAllByRole('link').map((a) => a.textContent)).toEqual(expected)
  })

  it('admin y gestor entran al dashboard operativo', async () => {
    for (const role of ['admin', 'tenant_manager'] as const) {
      const { unmount } = renderApp('/dashboard', fakeAuthApi(makeUser(role)))
      expect(await h1('Dashboard')).toBeInTheDocument()
      unmount()
    }
  })

  it('el cliente ve su panel de solo lectura con el nombre de su organización', async () => {
    renderApp('/dashboard', fakeAuthApi(makeUser('client')))
    expect(await h1('Mi panel')).toBeInTheDocument()
    expect(screen.getByText('Resultados de Clínica Vital.')).toBeInTheDocument()
    // Solo un subconjunto de indicadores.
    expect(screen.getByText('Conversaciones hoy')).toBeInTheDocument()
    expect(screen.queryByText('Tiempo de respuesta')).not.toBeInTheDocument()
  })

  it('el botmaster cae directamente en Agentes, con los agentes de su (único) tenant', async () => {
    // El tenant de este usuario (t1, de renderApp.tsx) tiene que existir de
    // verdad en la API admin para que createLangflowSession no falle con 404 -
    // el mock por defecto usa otros ids (t-vital…), por eso el seed explícito.
    renderApp('/dashboard', fakeAuthApi(makeUser('botmaster')), createMockAdminApi({ latencyMs: 0, seed: SEED }))
    expect(await h1('Agentes')).toBeInTheDocument()
    // Un solo tenant asignado: se auto-selecciona (TenantProvider), sin pedir elegir uno,
    // y abre en la pestaña de agentes registrados (el editor está en la otra).
    expect(await screen.findByRole('tab', { name: 'Agentes', selected: true })).toBeInTheDocument()
    expect(await screen.findByText('Recepción', undefined, { timeout: 5000 })).toBeInTheDocument()
    const [sidebar] = screen.getAllByRole('navigation', { name: 'Principal' })
    expect(within(sidebar!).getByRole('link', { name: 'Agentes' })).toHaveAttribute('aria-current', 'page')
  })

  it('el consultor cae en Reportes (placeholder de los futuros dashboards de Metabase)', async () => {
    renderApp('/dashboard', fakeAuthApi(makeUser('consultant')))
    expect(await h1('Reportes')).toBeInTheDocument()
    expect(screen.getByText(/dashboards de Metabase/)).toBeInTheDocument()
  })

  it.each<[Role, string]>([
    ['client', '/channels'],
    ['client', '/agents'],
    ['client', '/conversations'],
    ['botmaster', '/tenants'],
    ['client', '/tenants'],
    ['tenant_manager', '/users'],
    ['botmaster', '/users'],
    ['client', '/users'],
    ['consultant', '/channels'],
    ['consultant', '/agents'],
    ['consultant', '/conversations'],
    ['consultant', '/tenants'],
    ['consultant', '/users'],
    // "Mi empresa" es exclusivo de client (ni siquiera el admin la ve - la edita desde Tenants).
    ['admin', '/company'],
    ['botmaster', '/company'],
    ['consultant', '/company'],
  ])('%s recibe 403 al abrir %s por URL directa', async (role, path) => {
    renderApp(path, fakeAuthApi(makeUser(role)))
    expect(await h1('Sin acceso')).toBeInTheDocument()
  })

  it('el client puede abrir Mi empresa', async () => {
    renderApp('/company', fakeAuthApi(makeUser('client')))
    expect(await h1('Mi empresa')).toBeInTheDocument()
  })

  it.each(['/channels', '/conversations'])('el botmaster sí puede abrir %s (gestiona canales y conversaciones de sus tenants)', async (path) => {
    renderApp(path, fakeAuthApi(makeUser('botmaster')))
    expect(await h1(path === '/channels' ? 'Canales' : 'Conversaciones')).toBeInTheDocument()
  })

  it('solo el admin puede abrir /users', async () => {
    renderApp('/users', fakeAuthApi(makeUser('admin')))
    expect(await h1('Usuarios')).toBeInTheDocument()
  })

  it('todos los perfiles pueden abrir Ajustes', async () => {
    for (const role of ['admin', 'tenant_manager', 'botmaster', 'client', 'consultant'] as const) {
      const { unmount } = renderApp('/settings', fakeAuthApi(makeUser(role)))
      expect(await h1('Ajustes')).toBeInTheDocument()
      unmount()
    }
  })

  it('una ruta inexistente muestra el 404 dentro del shell', async () => {
    renderApp('/no-existe', fakeAuthApi(makeUser('admin')))
    expect(await h1('Página no encontrada')).toBeInTheDocument()
  })
})

describe('AppShell', () => {
  it('navegar por el menú cambia de vista', async () => {
    renderApp('/dashboard', fakeAuthApi(makeUser('admin')))
    await h1('Dashboard')
    const [sidebar] = screen.getAllByRole('navigation', { name: 'Principal' })
    await userEvent.click(within(sidebar!).getByRole('link', { name: 'Canales' }))
    expect(await h1('Canales')).toBeInTheDocument()
  })

  it('el contenido ocupa todo el ancho disponible (sin tope ni márgenes laterales automáticos)', async () => {
    renderApp('/dashboard', fakeAuthApi(makeUser('admin')))
    await h1('Dashboard')
    const main = screen.getByRole('main')
    expect(main).toHaveClass('w-full')
    expect(main.className).not.toMatch(/max-w-|mx-auto/)
  })

  it('contrae y expande la sidebar', async () => {
    renderApp('/dashboard', fakeAuthApi(makeUser('admin')))
    await userEvent.click(await screen.findByRole('button', { name: 'Contraer menú' }))
    expect(screen.getByRole('button', { name: 'Expandir menú' })).toBeInTheDocument()
  })

  it('Ctrl+K enfoca la búsqueda', async () => {
    renderApp('/dashboard', fakeAuthApi(makeUser('admin')))
    await h1('Dashboard')
    await userEvent.keyboard('{Control>}k{/Control}')
    expect(screen.getByRole('combobox', { name: 'Buscar' })).toHaveFocus()
  })

  it('el menú de usuario muestra el rol y permite cerrar sesión', async () => {
    renderApp('/dashboard', fakeAuthApi(makeUser('admin')))
    await userEvent.click(await screen.findByRole('button', { name: 'Menú de usuario' }))
    expect(screen.getByRole('button', { name: 'Cerrar sesión' })).toBeInTheDocument()
  })

  it('el selector de modo rota system -> light -> dark', async () => {
    renderApp('/dashboard', fakeAuthApi(makeUser('admin')))
    await userEvent.click(await screen.findByRole('button', { name: /Modo del sistema/ }))
    await userEvent.click(screen.getByRole('button', { name: /Modo claro/ }))
    expect(screen.getByRole('button', { name: /Modo oscuro/ })).toBeInTheDocument()
    expect(document.documentElement).toHaveClass('dark')
  })

  it('la búsqueda solo aparece para perfiles con algo que buscar', async () => {
    const admin = renderApp('/dashboard', fakeAuthApi(makeUser('admin')))
    await h1('Dashboard')
    expect(screen.getByRole('combobox', { name: 'Buscar' })).toBeInTheDocument()
    admin.unmount()

    renderApp('/dashboard', fakeAuthApi(makeUser('client')))
    await h1('Mi panel')
    expect(screen.queryByRole('combobox', { name: 'Buscar' })).not.toBeInTheDocument()
  })
})

describe('selector de tenant', () => {
  it('el administrador elige entre "todos" y cada tenant', async () => {
    renderApp('/dashboard', fakeAuthApi(makeUser('admin')))
    const select = await screen.findByRole('combobox', { name: 'Tenant activo' })
    expect(select).toHaveValue('all')
    expect(within(select).getAllByRole('option').map((o) => o.textContent)).toEqual([
      'Todos los tenants', 'Clínica Vital', 'Inmobiliaria Norte', 'Tienda Aurora',
    ])
    await userEvent.selectOptions(select, 't2')
    expect(select).toHaveValue('t2')
  })

  it('el gestor no tiene la opción "todos"', async () => {
    renderApp('/dashboard', fakeAuthApi(makeUser('tenant_manager')))
    const select = await screen.findByRole('combobox', { name: 'Tenant activo' })
    expect(within(select).queryByRole('option', { name: 'Todos los tenants' })).not.toBeInTheDocument()
  })

  it('con un solo tenant se muestra como etiqueta, sin selector', async () => {
    renderApp('/dashboard', fakeAuthApi(makeUser('client')))
    await h1('Mi panel')
    expect(screen.queryByRole('combobox', { name: 'Tenant activo' })).not.toBeInTheDocument()
    expect(screen.getAllByText('Clínica Vital').length).toBeGreaterThan(0)
  })
})

describe('menú de usuario', () => {
  it('muestra nombre, correo y perfil, y cierra sesión volviendo a /login', async () => {
    renderApp('/dashboard', fakeAuthApi(makeUser('botmaster')))
    await userEvent.click(await screen.findByRole('button', { name: 'Menú de usuario' }))
    expect(screen.getByText('Persona botmaster')).toBeInTheDocument()
    expect(screen.getByText('botmaster@test.dev')).toBeInTheDocument()
    expect(screen.getByText('Botmaster')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Cerrar sesión' }))
    expect(await h1('Inicia sesión')).toBeInTheDocument()
  })

  it('se cierra con Escape', async () => {
    renderApp('/dashboard', fakeAuthApi(makeUser('admin')))
    await userEvent.click(await screen.findByRole('button', { name: 'Menú de usuario' }))
    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('button', { name: 'Cerrar sesión' })).not.toBeInTheDocument()
  })
})

describe('ruta raíz', () => {
  it('sin sesión muestra el login', async () => {
    renderApp('/', fakeAuthApi(null))
    expect(await h1('Inicia sesión')).toBeInTheDocument()
  })

  it.each<[Role, string]>([
    ['admin', 'Dashboard'],
    ['tenant_manager', 'Dashboard'],
    ['client', 'Mi panel'],
    ['botmaster', 'Agentes'],
    ['consultant', 'Reportes'],
  ])('con sesión %s lleva a su inicio (%s)', async (role, title) => {
    renderApp('/', fakeAuthApi(makeUser(role)))
    expect(await h1(title)).toBeInTheDocument()
  })
})

describe('con sesión activa /login no se muestra', () => {
  it('redirige a la página de inicio del perfil', async () => {
    renderApp('/login', fakeAuthApi(makeUser('botmaster')))
    expect(await h1('Agentes')).toBeInTheDocument()
    await waitFor(() => expect(screen.queryByText('Inicia sesión')).not.toBeInTheDocument())
  })
})
