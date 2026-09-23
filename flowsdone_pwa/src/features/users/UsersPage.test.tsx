import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { createMockAdminApi } from '@/core/admin/mockAdminApi'
import { SEED } from '@/test/adminFixtures'
import { fakeAuthApi, makeUser, renderApp } from '@/test/renderApp'

const mock = () => createMockAdminApi({ latencyMs: 0, seed: SEED })

async function open(api = mock()) {
  renderApp('/usuarios', fakeAuthApi(makeUser('admin')), api)
  await screen.findByRole('heading', { level: 1, name: 'Usuarios' })
  await screen.findByRole('list', { name: 'Usuarios' })
  return api
}
const list = () => screen.getByRole('list', { name: 'Usuarios' })

describe('UsersPage', () => {
  it('lista el staff con su rol y estado, y deja fuera a los client', async () => {
    await open()
    expect(within(list()).getByText('Ana Admin')).toBeInTheDocument()
    expect(within(list()).getByText('Marcos Gestor')).toBeInTheDocument()
    expect(within(list()).getByText('Bea Botmaster')).toBeInTheDocument()
    expect(within(list()).queryByText('Carla Cliente')).not.toBeInTheDocument()
    expect(within(list()).getByText('Pendiente de activar')).toBeInTheDocument()
  })

  it('crea un usuario: queda pending y pide tenants salvo para admin', async () => {
    await open()
    await userEvent.click(screen.getByRole('button', { name: /Nuevo usuario/ }))
    const dialog = screen.getByRole('dialog', { name: 'Nuevo usuario' })

    // Por defecto pide tenants (botmaster); elegir Administrador los oculta.
    expect(within(dialog).getByText('Tenants')).toBeInTheDocument()
    await userEvent.selectOptions(within(dialog).getByLabelText('Rol'), 'Administrador')
    expect(within(dialog).queryByText('Tenants')).not.toBeInTheDocument()

    await userEvent.selectOptions(within(dialog).getByLabelText('Rol'), 'Botmaster')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Crear usuario' }))
    expect(within(dialog).getByText('Escribe un email válido.')).toBeInTheDocument()
    expect(within(dialog).getByText('El nombre es obligatorio.')).toBeInTheDocument()
    expect(within(dialog).getByText('Elige al menos un tenant.')).toBeInTheDocument()

    await userEvent.type(within(dialog).getByLabelText('Email'), 'nuevo@flowsdone.com')
    await userEvent.type(within(dialog).getByLabelText('Nombre'), 'Nuevo Botmaster')
    await userEvent.click(within(dialog).getByLabelText('Clínica Vital'))
    await userEvent.click(within(dialog).getByRole('button', { name: 'Crear usuario' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(within(list()).getByText('Nuevo Botmaster')).toBeInTheDocument()
  })

  it('crea un consultor (consultores de clientes, acotados a reportes)', async () => {
    await open()
    await userEvent.click(screen.getByRole('button', { name: /Nuevo usuario/ }))
    const dialog = screen.getByRole('dialog', { name: 'Nuevo usuario' })

    await userEvent.selectOptions(within(dialog).getByLabelText('Rol'), 'Consultor')
    expect(within(dialog).getByText('Tenants')).toBeInTheDocument() // igual que botmaster/gestor: pide tenant(s)

    await userEvent.type(within(dialog).getByLabelText('Email'), 'consultor@cliente.com')
    await userEvent.type(within(dialog).getByLabelText('Nombre'), 'Cecilia Consultora')
    await userEvent.click(within(dialog).getByLabelText('Clínica Vital'))
    await userEvent.click(within(dialog).getByRole('button', { name: 'Crear usuario' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(within(list()).getByText('Cecilia Consultora')).toBeInTheDocument()
    expect(within(list()).getByText('Consultor')).toBeInTheDocument()
  })

  it('edita el rol y el estado de un usuario', async () => {
    await open()
    await userEvent.click(within(list()).getByRole('button', { name: 'Editar Marcos Gestor' }))
    const dialog = screen.getByRole('dialog', { name: 'Editar usuario' })
    expect(within(dialog).getByLabelText('Email')).toBeDisabled()

    await userEvent.selectOptions(within(dialog).getByLabelText('Estado'), 'disabled')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Guardar cambios' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(within(list()).getByText('Deshabilitado')).toBeInTheDocument()
  })

  it('reenvía la activación de un usuario pending y avisa del resultado', async () => {
    await open()
    await userEvent.click(within(list()).getByRole('button', { name: /Reenviar email de activación a Bea Botmaster/ }))
    expect(await screen.findByText(/Se reenvió el email de activación a bea@flowsdone.com/)).toBeInTheDocument()
  })

  it('el aviso de reenvío se puede quitar', async () => {
    await open()
    await userEvent.click(within(list()).getByRole('button', { name: /Reenviar email de activación a Bea Botmaster/ }))
    await screen.findByText(/Se reenvió el email de activación/)

    await userEvent.click(screen.getByRole('button', { name: 'Quitar aviso' }))
    expect(screen.queryByText(/Se reenvió el email de activación/)).not.toBeInTheDocument()
  })

  it('un reenvío que falla también avisa (usuario ya no pending)', async () => {
    const api = mock()
    await open(api)
    // Se activó justo después de cargar la lista (fuera de esta pantalla): la fila
    // en pantalla sigue mostrando "pending" un instante, pero el backend ya no.
    await api.updateUser('u3', { status: 'active' })
    await userEvent.click(within(list()).getByRole('button', { name: /Reenviar email de activación a Bea Botmaster/ }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/ya no existe|no tienes acceso/)
  })

  it('elimina un usuario con confirmación', async () => {
    await open()
    await userEvent.click(within(list()).getByRole('button', { name: 'Eliminar Bea Botmaster' }))
    const confirm = screen.getByRole('dialog', { name: 'Eliminar usuario' })
    expect(within(confirm).getByText(/Bea Botmaster/)).toBeInTheDocument()
    await userEvent.click(within(confirm).getByRole('button', { name: 'Eliminar' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(within(list()).queryByText('Bea Botmaster')).not.toBeInTheDocument()
  })
})
