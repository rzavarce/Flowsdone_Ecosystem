import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
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
  it.each(['/', '/dashboard', '/canales', '/agentes', '/ajustes'])('%s redirige a /login', async (path) => {
    renderApp(path, fakeAuthApi(null))
    expect(await h1('Inicia sesión')).toBeInTheDocument()
  })
})

describe('menú y acceso por perfil', () => {
  it.each<[Role, string[]]>([
    ['admin', ['Dashboard', 'Conversaciones', 'Canales', 'Tenants', 'Agentes', 'Ajustes']],
    ['tenant_manager', ['Dashboard', 'Conversaciones', 'Canales', 'Tenants', 'Agentes', 'Ajustes']],
    ['botmaster', ['Agentes', 'Ajustes']],
    ['client', ['Dashboard', 'Ajustes']],
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

  it('el botmaster cae directamente en Agentes (la lista de su tenant, sin editor de Langflow)', async () => {
    renderApp('/dashboard', fakeAuthApi(makeUser('botmaster')))
    expect(await h1('Agentes')).toBeInTheDocument()
    // El botmaster no recibe el editor de Langflow (ver AgentsPage): solo la lista de su tenant.
    expect(screen.queryByText(/se embeberá Langflow/)).not.toBeInTheDocument()
    expect(await screen.findByText(/es solo para el equipo de la plataforma/)).toBeInTheDocument()
    const [sidebar] = screen.getAllByRole('navigation', { name: 'Principal' })
    expect(within(sidebar!).getByRole('link', { name: 'Agentes' })).toHaveAttribute('aria-current', 'page')
  })

  it.each<[Role, string]>([
    ['botmaster', '/canales'],
    ['botmaster', '/conversaciones'],
    ['client', '/canales'],
    ['client', '/agentes'],
    ['client', '/conversaciones'],
    ['botmaster', '/tenants'],
    ['client', '/tenants'],
  ])('%s recibe 403 al abrir %s por URL directa', async (role, path) => {
    renderApp(path, fakeAuthApi(makeUser(role)))
    expect(await h1('Sin acceso')).toBeInTheDocument()
  })

  it('todos los perfiles pueden abrir Ajustes', async () => {
    for (const role of ['admin', 'tenant_manager', 'botmaster', 'client'] as const) {
      const { unmount } = renderApp('/ajustes', fakeAuthApi(makeUser(role)))
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

  it('el selector de modo rota system -> light -> dark', async () => {
    renderApp('/dashboard', fakeAuthApi(makeUser('admin')))
    await userEvent.click(await screen.findByRole('button', { name: /Modo del sistema/ }))
    await userEvent.click(screen.getByRole('button', { name: /Modo claro/ }))
    expect(screen.getByRole('button', { name: /Modo oscuro/ })).toBeInTheDocument()
    expect(document.documentElement).toHaveClass('dark')
  })

  it('la búsqueda solo aparece para perfiles que operan conversaciones', async () => {
    const admin = renderApp('/dashboard', fakeAuthApi(makeUser('admin')))
    await h1('Dashboard')
    expect(screen.getByRole('searchbox', { name: 'Buscar' })).toBeInTheDocument()
    admin.unmount()

    renderApp('/dashboard', fakeAuthApi(makeUser('client')))
    await h1('Mi panel')
    expect(screen.queryByRole('searchbox')).not.toBeInTheDocument()
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
