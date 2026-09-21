import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RouterProvider, createMemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { ThemeProvider } from '@/core/theme/ThemeProvider'
import { NAV_ITEMS } from '@/components/layout/navigation'
import { routes } from './router'

const renderAt = (path: string) =>
  render(
    <ThemeProvider>
      <RouterProvider router={createMemoryRouter(routes, { initialEntries: [path] })} />
    </ThemeProvider>,
  )

describe('rutas', () => {
  it.each([
    ['/', 'Dashboard'],
    ['/conversaciones', 'Conversaciones'],
    ['/canales', 'Canales'],
    ['/workflows', 'Workflows'],
    ['/ajustes', 'Ajustes'],
  ])('%s renderiza su título', (path, title) => {
    renderAt(path)
    expect(screen.getByRole('heading', { level: 1, name: title })).toBeInTheDocument()
  })

  it('una ruta inexistente muestra el 404 dentro del shell', () => {
    renderAt('/no-existe')
    expect(screen.getByRole('heading', { level: 1, name: 'Página no encontrada' })).toBeInTheDocument()
    expect(screen.getAllByRole('navigation', { name: 'Principal' }).length).toBeGreaterThan(0)
  })
})

describe('AppShell', () => {
  it('expone todos los items en sidebar y barra móvil', () => {
    renderAt('/')
    const navs = screen.getAllByRole('navigation', { name: 'Principal' })
    expect(navs).toHaveLength(2)
    for (const nav of navs) {
      for (const item of NAV_ITEMS) {
        expect(within(nav).getByRole('link', { name: item.label })).toBeInTheDocument()
      }
    }
  })

  it('navegar por el menú cambia de vista', async () => {
    renderAt('/')
    const [sidebar] = screen.getAllByRole('navigation', { name: 'Principal' })
    await userEvent.click(within(sidebar!).getByRole('link', { name: 'Canales' }))
    expect(screen.getByRole('heading', { level: 1, name: 'Canales' })).toBeInTheDocument()
  })

  it('contrae y expande la sidebar', async () => {
    renderAt('/')
    await userEvent.click(screen.getByRole('button', { name: 'Contraer menú' }))
    expect(screen.getByRole('button', { name: 'Expandir menú' })).toBeInTheDocument()
  })

  it('el selector de modo de la barra superior rota light -> dark -> system', async () => {
    renderAt('/')
    // Arranca en "system": el siguiente es claro.
    await userEvent.click(screen.getByRole('button', { name: /Modo del sistema/ }))
    expect(screen.getByRole('button', { name: /Modo claro/ })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Modo claro/ }))
    expect(screen.getByRole('button', { name: /Modo oscuro/ })).toBeInTheDocument()
    expect(document.documentElement).toHaveClass('dark')
  })
})
