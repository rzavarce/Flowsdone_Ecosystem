import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { createMockAdminApi } from '@/core/admin/mockAdminApi'
import { SEED } from '@/test/adminFixtures'
import { fakeAuthApi, makeUser, renderApp } from '@/test/renderApp'

const setup = (role: 'admin' | 'botmaster' = 'admin') => {
  const admin = createMockAdminApi({ latencyMs: 0, seed: SEED })
  renderApp('/contacts', fakeAuthApi(makeUser(role)), admin)
  return admin
}

const contactList = () => screen.findByRole('list', { name: 'Contactos' }, { timeout: 5000 })

describe('ContactsPage', { timeout: 20_000 }, () => {
  it('lista los contactos y al abrir uno muestra su ficha y sus últimas conversaciones', async () => {
    setup()
    const scroll = vi.spyOn(window, 'scrollTo')
    const items = within(await contactList()).getAllByRole('button')
    expect(items.length).toBeGreaterThan(0)

    await userEvent.click(items[0]!)
    // The detail is at the top: the page scrolls up to it.
    expect(scroll).toHaveBeenCalledWith(expect.objectContaining({ top: 0 }))

    expect(await screen.findByText('Identificador del canal', {}, { timeout: 5000 })).toBeInTheDocument()
    const recent = screen.getByRole('list', { name: 'Últimas conversaciones' })
    const links = within(recent).getAllByRole('link')
    expect(links.length).toBeGreaterThan(0)
    expect(links.length).toBeLessThanOrEqual(5)
    expect(links[0]).toHaveAttribute('href', expect.stringMatching(/^\/conversations\?c=/))
  })

  it('busca por nombre, teléfono o usuario y filtra por canal', async () => {
    const admin = setup()
    const list = vi.spyOn(admin, 'listContacts')
    await contactList()

    await userEvent.type(screen.getByLabelText('Buscar contacto'), 'usuario11')
    await vi.waitFor(() => expect(within(screen.getByRole('list', { name: 'Contactos' })).getAllByRole('button')).toHaveLength(1))
    expect(list).toHaveBeenLastCalledWith(expect.objectContaining({ q: 'usuario11' }))

    await userEvent.clear(screen.getByLabelText('Buscar contacto'))
    await userEvent.selectOptions(screen.getByLabelText('Canal'), 'demo')
    await vi.waitFor(() => expect(list).toHaveBeenLastCalledWith(expect.objectContaining({ channel_type: 'demo' })))
    const [demo] = within(await contactList()).getAllByRole('button')
    expect(demo).toHaveTextContent('Demo · visitante 1a2b3c4d')
  })

  it('se edita la ficha desde el contacto y el nombre aparece en la lista', async () => {
    const admin = setup()
    const update = vi.spyOn(admin, 'updateContact')
    await userEvent.click(within(await contactList()).getAllByRole('button')[0]!)

    await userEvent.click(await screen.findByRole('button', { name: 'Añadir datos' }, { timeout: 5000 }))
    const dialog = screen.getByRole('dialog', { name: 'Editar contacto' })
    await userEvent.type(within(dialog).getByLabelText('Nombre'), 'Ana Pérez')
    await userEvent.type(within(dialog).getByLabelText('Usuario / cuenta'), '@ana')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Guardar' }))

    expect(update).toHaveBeenCalledWith(expect.any(String), { name: 'Ana Pérez', username: '@ana' })
    expect(await screen.findByRole('heading', { name: 'Ana Pérez' }, { timeout: 5000 })).toBeInTheDocument()
    await vi.waitFor(() => expect(within(screen.getByRole('list', { name: 'Contactos' })).getAllByRole('button')[0]).toHaveTextContent('Ana Pérez'))
  })

  it('sin resultados muestra el estado vacío', async () => {
    setup()
    await contactList()
    await userEvent.type(screen.getByLabelText('Buscar contacto'), 'nadie-con-este-nombre')
    expect(await screen.findByText('No hay contactos')).toBeInTheDocument()
  })
})
