import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { createMockAdminApi } from '@/core/admin/mockAdminApi'
import { SEED } from '@/test/adminFixtures'
import { fakeAuthApi, makeUser, renderApp } from '@/test/renderApp'

/** Agents page on tenant t1 (project p1: Recepción [default, with channel] and Citas). */
async function setup(tenant = 't1') {
  const admin = createMockAdminApi({ latencyMs: 0, seed: SEED })
  renderApp('/agents', fakeAuthApi(makeUser('admin')), admin)
  await userEvent.selectOptions(await screen.findByRole('combobox', { name: 'Tenant activo' }, { timeout: 5000 }), tenant)
  // La página abre en el editor de flujos; el registro de agentes está en la otra pestaña.
  await userEvent.click(await screen.findByRole('tab', { name: 'Agentes' }))
  return admin
}

const agentRows = async () =>
  within(await screen.findByRole('list', { name: 'Atención' }, { timeout: 5000 })).getAllByRole('listitem')

describe('Agentes: registro y gestión', { timeout: 20_000 }, () => {
  it('lista los agentes del proyecto con su flujo y cuál es el predeterminado', async () => {
    await setup()
    const [recepcion, citas] = await agentRows()
    expect(recepcion).toHaveTextContent('Recepción')
    expect(recepcion).toHaveTextContent('Predeterminado')
    expect(await within(recepcion).findByText('Flujo: Flujo de Recepción')).toBeInTheDocument()
    expect(citas).not.toHaveTextContent('Predeterminado')
  })

  it('registra un flujo de la carpeta del proyecto; el nombre sigue al flujo y los ya registrados no se pueden elegir', async () => {
    const admin = await setup()
    const create = vi.spyOn(admin, 'createAgent')
    await agentRows()
    await userEvent.click(screen.getByRole('button', { name: 'Registrar agente' }))
    const dialog = within(screen.getByRole('dialog'))
    const flow = await dialog.findByLabelText('Flujo de Langflow')
    expect(within(flow).getByRole('option', { name: 'Flujo de Recepción (ya registrado)' })).toBeDisabled()

    await userEvent.selectOptions(flow, 'p1-flow-asistente')
    expect(dialog.getByLabelText('Nombre del agente')).toHaveValue('Asistente de ventas')
    await userEvent.click(dialog.getByRole('button', { name: 'Guardar' }))

    expect(create).toHaveBeenCalledWith({
      project_id: 'p1', name: 'Asistente de ventas', langflow_flow_id: 'p1-flow-asistente', is_default: false,
    })
    expect(await screen.findByText('Asistente de ventas', { selector: '.font-medium' })).toBeInTheDocument()
  })

  it('exige elegir un flujo', async () => {
    const admin = await setup()
    const create = vi.spyOn(admin, 'createAgent')
    await agentRows()
    await userEvent.click(screen.getByRole('button', { name: 'Registrar agente' }))
    const dialog = within(screen.getByRole('dialog'))
    await dialog.findByLabelText('Flujo de Langflow')
    await userEvent.click(dialog.getByRole('button', { name: 'Guardar' }))
    expect(dialog.getByText('Elige un flujo.')).toBeInTheDocument()
    expect(create).not.toHaveBeenCalled()
  })

  it('hacer predeterminado a otro agente le quita la marca al anterior', async () => {
    const admin = await setup()
    const update = vi.spyOn(admin, 'updateAgent')
    await agentRows()
    await userEvent.click(screen.getByRole('button', { name: 'Hacer predeterminado a Citas' }))
    expect(update).toHaveBeenCalledWith('a1b', { is_default: true })
    const [recepcion] = await agentRows()
    await vi.waitFor(() => expect(recepcion).not.toHaveTextContent('Predeterminado'))
  })

  it('no deja eliminar un agente con canales y permite suspenderlo', async () => {
    await setup()
    await agentRows()
    await userEvent.click(screen.getByRole('button', { name: 'Eliminar Recepción' }))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Eliminar agente' }))
    expect(await screen.findByText(/tiene canales conectados/)).toBeInTheDocument()
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Cancelar' }))

    await userEvent.click(screen.getByRole('button', { name: 'Suspender Citas' }))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Suspender agente' }))
    const [, citas] = await agentRows()
    await vi.waitFor(() => expect(citas).toHaveTextContent('Suspendido'))
    expect(screen.getByRole('button', { name: 'Reactivar Citas' })).toBeInTheDocument()
  })

  it('"Probar en webchat" abre la demo con un enlace firmado para ese agente', async () => {
    const admin = await setup()
    const link = vi.spyOn(admin, 'webchatTestLink').mockResolvedValue({ url: 'https://chat.flowsdone.com/?test_token=x', expires_in: 1800 })
    const tab = { location: { href: '' }, close: vi.fn() }
    const openWindow = vi.spyOn(window, 'open').mockReturnValue(tab as unknown as Window)
    await agentRows()

    await userEvent.click(screen.getByRole('button', { name: 'Probar Recepción en webchat' }))

    expect(openWindow).toHaveBeenCalledWith('', '_blank')
    expect(link).toHaveBeenCalledWith('a1')
    await vi.waitFor(() => expect(tab.location.href).toBe('https://chat.flowsdone.com/?test_token=x'))
    openWindow.mockRestore()
  })

  it('"Compartir" crea por defecto un enlace sin vencimiento y lo muestra para copiarlo', async () => {
    const admin = await setup()
    const create = vi.spyOn(admin, 'createWebchatShare')
    await agentRows()

    await userEvent.click(screen.getByRole('button', { name: 'Compartir Recepción' }))
    const dialog = within(screen.getByRole('dialog', { name: 'Compartir Recepción' }))
    expect(dialog.getByRole('radio', { name: 'Sin vencimiento' })).toHaveAttribute('aria-checked', 'true')
    expect(await dialog.findByText('Este agente todavía no tiene enlaces compartidos.')).toBeInTheDocument()

    await userEvent.click(dialog.getByRole('button', { name: 'Crear enlace' }))

    expect(create).toHaveBeenCalledWith('a1', null)
    const url = await dialog.findByRole('textbox', { name: 'Enlace compartido' })
    expect((url as HTMLInputElement).value).toMatch(/^https:\/\/chat\.flowsdone\.com\/\?share=/)
    expect(dialog.getByText('Sin vencimiento', { selector: 'span' })).toBeInTheDocument()
  })

  it('"Compartir" permite elegir 7 o 30 días', async () => {
    const admin = await setup()
    const create = vi.spyOn(admin, 'createWebchatShare')
    await agentRows()
    await userEvent.click(screen.getByRole('button', { name: 'Compartir Recepción' }))
    const dialog = within(screen.getByRole('dialog'))

    await userEvent.click(dialog.getByRole('radio', { name: '30 días' }))
    await userEvent.click(dialog.getByRole('button', { name: 'Crear enlace' }))
    await userEvent.click(dialog.getByRole('radio', { name: '7 días' }))
    await userEvent.click(dialog.getByRole('button', { name: 'Crear enlace' }))

    await vi.waitFor(() => expect(create.mock.calls).toEqual([['a1', 30], ['a1', 7]]))
    await vi.waitFor(() => expect(dialog.getAllByText(/^Vence el /)).toHaveLength(2))
  })

  it('revocar un enlace pide confirmación y lo quita de la lista', async () => {
    const admin = await setup()
    const revoke = vi.spyOn(admin, 'revokeWebchatShare')
    await admin.createWebchatShare('a1', null)
    await agentRows()
    await userEvent.click(screen.getByRole('button', { name: 'Compartir Recepción' }))
    const dialog = within(screen.getByRole('dialog'))
    await dialog.findByRole('textbox', { name: 'Enlace compartido' })

    await userEvent.click(dialog.getByRole('button', { name: 'Revocar' }))
    expect(dialog.getByText(/Dejará de funcionar al instante/)).toBeInTheDocument()
    expect(revoke).not.toHaveBeenCalled()
    await userEvent.click(dialog.getByRole('button', { name: 'Revocar' }))

    expect(revoke).toHaveBeenCalledWith('a1', expect.any(String))
    expect(await dialog.findByText('Este agente todavía no tiene enlaces compartidos.')).toBeInTheDocument()
  })

  it('un agente suspendido no se puede compartir', async () => {
    await setup()
    await agentRows()
    expect(screen.getByRole('button', { name: 'Compartir Citas' })).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Suspender Citas' }))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Suspender agente' }))

    const [, citas] = await agentRows()
    await vi.waitFor(() => expect(citas).toHaveTextContent('Suspendido'))
    expect(within(citas).queryByRole('button', { name: 'Compartir Citas' })).not.toBeInTheDocument()
  })

  it('un tenant sin proyectos explica que hay que crear uno', async () => {
    await setup('t3')
    expect(await screen.findByText(/no tiene proyectos todavía/, undefined, { timeout: 5000 })).toBeInTheDocument()
  })
})
