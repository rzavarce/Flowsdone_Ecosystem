import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { createMockAdminApi } from '@/core/admin/mockAdminApi'
import { SEED } from '@/test/adminFixtures'
import { fakeAuthApi, makeUser, renderApp } from '@/test/renderApp'

const setup = () => {
  const admin = createMockAdminApi({ latencyMs: 0, seed: SEED })
  renderApp('/users', fakeAuthApi(makeUser('admin')), admin)
  return admin
}

// Mucho tecleo (userEvent.type) por test: con la suite completa en paralelo pasa de 5 s.
describe('UsersPage: datos de perfil opcionales', { timeout: 20_000 }, () => {
  it('crear un usuario manda teléfono, dirección y redes solo si se rellenan', async () => {
    const admin = setup()
    const create = vi.spyOn(admin, 'createUser')
    await userEvent.click(await screen.findByRole('button', { name: 'Nuevo usuario' }))
    const dialog = within(screen.getByRole('dialog'))
    await userEvent.type(dialog.getByLabelText('Email'), 'nueva@flowsdone.com')
    await userEvent.type(dialog.getByLabelText('Nombre'), 'Nueva Persona')
    await userEvent.click(dialog.getAllByRole('checkbox')[0]!)
    await userEvent.type(dialog.getByLabelText(/Teléfono/), '+34 600 000 000')
    await userEvent.type(dialog.getByLabelText('Sitio web'), 'https://nueva.dev')
    await userEvent.click(dialog.getByRole('button', { name: 'Crear usuario' }))

    expect(create).toHaveBeenCalledWith(
      expect.objectContaining({ phone: '+34 600 000 000', social_links: { website: 'https://nueva.dev' } }),
    )
    expect(create.mock.calls[0]![0]).not.toHaveProperty('address')
  })

  it('una URL inválida bloquea el envío y lo explica', async () => {
    const admin = setup()
    const create = vi.spyOn(admin, 'createUser')
    await userEvent.click(await screen.findByRole('button', { name: 'Nuevo usuario' }))
    const dialog = within(screen.getByRole('dialog'))
    await userEvent.type(dialog.getByLabelText('Email'), 'otra@flowsdone.com')
    await userEvent.type(dialog.getByLabelText('Nombre'), 'Otra')
    await userEvent.click(dialog.getAllByRole('checkbox')[0]!)
    await userEvent.type(dialog.getByLabelText('Instagram'), 'javascript:alert(1)')
    await userEvent.click(dialog.getByRole('button', { name: 'Crear usuario' }))

    expect(dialog.getByText(/empiece por https/)).toBeInTheDocument()
    expect(create).not.toHaveBeenCalled()
  })

  it('al editar se puede cambiar la dirección y aparece la sección de foto', async () => {
    const admin = setup()
    const update = vi.spyOn(admin, 'updateUser')
    const [first] = await screen.findAllByRole('button', { name: /^Editar / })
    await userEvent.click(first!)
    const dialog = within(screen.getByRole('dialog'))
    expect(dialog.getByLabelText('Subir foto')).toBeInTheDocument()
    await userEvent.type(dialog.getByLabelText(/Dirección/), 'Av. Siempre Viva 742')
    await userEvent.click(dialog.getByRole('button', { name: 'Guardar cambios' }))
    expect(update).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({ address: 'Av. Siempre Viva 742' }))
  })
})
