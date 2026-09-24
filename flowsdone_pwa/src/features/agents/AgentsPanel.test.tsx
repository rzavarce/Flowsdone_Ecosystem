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

  it('un tenant sin proyectos explica que hay que crear uno', async () => {
    await setup('t3')
    expect(await screen.findByText(/no tiene proyectos todavía/, undefined, { timeout: 5000 })).toBeInTheDocument()
  })
})
