import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { createMockAdminApi } from '@/core/admin/mockAdminApi'
import type { Role } from '@/core/auth/types'
import { SEED } from '@/test/adminFixtures'
import { fakeAuthApi, makeUser, renderApp } from '@/test/renderApp'

const setup = (role: Role = 'admin', path = '/dashboard') => {
  renderApp(path, fakeAuthApi(makeUser(role)), createMockAdminApi({ latencyMs: 0, seed: SEED }))
}

const searchBox = () => screen.findByRole('combobox', { name: 'Buscar' })
const results = () => screen.getByRole('listbox', { name: 'Resultados de la búsqueda' })

describe('GlobalSearch', { timeout: 20_000 }, () => {
  it('agrupa lo que el perfil puede ver: secciones, tenants, agentes y canales', async () => {
    setup()
    await userEvent.type(await searchBox(), 'clin')

    expect(await within(results()).findByRole('option', { name: /Clínica Vital/ })).toBeInTheDocument()
    expect(await within(results()).findByRole('option', { name: /WhatsApp Clínica/ })).toBeInTheDocument()
    expect(within(results()).getByText('Tenants')).toBeInTheDocument()
    expect(within(results()).getByText('Canales')).toBeInTheDocument()
  })

  it('pide al menos 2 caracteres y avisa cuando no hay resultados', async () => {
    setup()
    const box = await searchBox()
    await userEvent.type(box, 'x')
    expect(await screen.findByText('Escribe al menos 2 caracteres')).toBeInTheDocument()

    await userEvent.type(box, 'yzq')
    expect(await screen.findByText('Sin resultados para «xyzq»')).toBeInTheDocument()
  })

  it('con el teclado: ↓ y Enter abre el resultado; un agente activa su tenant', async () => {
    setup()
    const box = await searchBox()
    await userEvent.type(box, 'asesor')
    await within(results()).findByRole('option', { name: /Asesor/ })

    await userEvent.keyboard('{ArrowDown}{ArrowUp}{Enter}')

    expect(await screen.findByRole('heading', { level: 1, name: 'Agentes' })).toBeInTheDocument()
    expect(screen.getAllByText('Inmobiliaria Norte').length).toBeGreaterThan(0)
    expect(box).toHaveValue('')
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  })

  it('un usuario del staff abre Usuarios filtrado por su email', async () => {
    setup()
    await userEvent.type(await searchBox(), 'marcos')
    await userEvent.click(await within(results()).findByRole('option', { name: /Marcos Gestor/ }))

    expect(await screen.findByRole('heading', { level: 1, name: 'Usuarios' })).toBeInTheDocument()
    expect(await screen.findByLabelText('Buscar usuario')).toHaveValue('marcos@flowsdone.com')
    expect(screen.getByText('Marcos Gestor')).toBeInTheDocument()
    expect(screen.queryByText('Bea Botmaster')).not.toBeInTheDocument()
  })

  it('una conversación se abre directamente con su transcripción', async () => {
    setup()
    await userEvent.type(await searchBox(), '@usuario1')
    const [first] = await within(results()).findAllByRole('option', undefined, { timeout: 5000 })
    await userEvent.click(first!)

    expect(await screen.findByRole('list', { name: 'Transcripción' }, { timeout: 5000 })).toBeInTheDocument()
  })

  it('Escape cierra los resultados', async () => {
    setup()
    await userEvent.type(await searchBox(), 'clin')
    await within(results()).findByRole('option', { name: /Clínica Vital/ })

    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  })

  it('un cliente no tiene buscador', async () => {
    setup('client')
    expect(await screen.findByRole('button', { name: 'Menú de usuario' })).toBeInTheDocument()
    expect(screen.queryByRole('combobox', { name: 'Buscar' })).not.toBeInTheDocument()
  })
})
