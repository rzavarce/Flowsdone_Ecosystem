import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { AdminApi } from '@/core/admin/AdminApi'
import { createMockAdminApi } from '@/core/admin/mockAdminApi'
import { SEED } from '@/test/adminFixtures'
import { fakeAuthApi, makeUser, renderApp } from '@/test/renderApp'
import type { Role } from '@/core/auth/types'

const seeded = (over: Partial<AdminApi> = {}): AdminApi => ({ ...createMockAdminApi({ latencyMs: 0, seed: SEED }), ...over })

async function open(role: Role = 'admin', api: AdminApi = seeded()) {
  renderApp('/integrations', fakeAuthApi(makeUser(role)), api)
  await screen.findByRole('heading', { level: 1, name: 'Integraciones' })
  await screen.findByRole('heading', { name: 'Webhook genérico' })
  return api
}
const webhookCard = () => screen.getByRole('heading', { name: 'Webhook genérico' }).closest('div.flex.flex-col') as HTMLElement

describe('Integraciones (CRM)', () => {
  it('muestra el webhook genérico para conectar y los CRM nativos como "Próximamente"', async () => {
    await open()
    expect(screen.getByRole('button', { name: 'Conectar' })).toBeInTheDocument()
    for (const name of ['Zendesk', 'Salesforce', 'Jira Service Management', 'Zoho Desk']) {
      expect(screen.getByRole('heading', { name })).toBeInTheDocument()
    }
    expect(screen.getAllByText('Próximamente')).toHaveLength(4)
  })

  it('conectar valida la URL, muestra el rechazo del gateway y después enseña los secretos una sola vez', async () => {
    const api = await open()
    const create = vi.spyOn(api, 'createCrmIntegration')
    await userEvent.click(screen.getByRole('button', { name: 'Conectar' }))
    const dialog = screen.getByRole('dialog', { name: 'Conectar un CRM por webhook' })

    await userEvent.type(within(dialog).getByLabelText('URL del webhook'), 'no-es-una-url')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Conectar' }))
    expect(within(dialog).getByText('Introduce una URL completa (https://…).')).toBeInTheDocument()
    expect(create).not.toHaveBeenCalled()

    await userEvent.clear(within(dialog).getByLabelText('URL del webhook'))
    await userEvent.type(within(dialog).getByLabelText('URL del webhook'), 'http://inseguro.com/x')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Conectar' }))
    expect(await within(dialog).findByText(/only https callbacks are allowed/)).toBeInTheDocument()

    await userEvent.clear(within(dialog).getByLabelText('URL del webhook'))
    await userEvent.type(within(dialog).getByLabelText('URL del webhook'), 'https://crm.cliente.com/hook')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Conectar' }))

    const secrets = await screen.findByRole('dialog', { name: 'Secretos de la integración' })
    expect(within(secrets).getByText(/Solo se muestran ahora/)).toBeInTheDocument()
    expect(within(secrets).getByText(/^sig-/)).toBeInTheDocument()
    expect(within(secrets).getByText(/^key-/)).toBeInTheDocument()
    await userEvent.click(within(secrets).getByRole('button', { name: 'Ya los he guardado' }))

    await waitFor(() => expect(within(webhookCard()).getByText('https://crm.cliente.com/hook')).toBeInTheDocument())
    expect(screen.queryByText(/^key-/)).not.toBeInTheDocument()
    expect(within(webhookCard()).getByText('Activo')).toBeInTheDocument()
  })

  it('probar, desactivar y rotar secretos desde la tarjeta', async () => {
    const api = await open()
    await userEvent.click(screen.getByRole('button', { name: 'Conectar' }))
    await userEvent.type(screen.getByLabelText('URL del webhook'), 'https://crm.cliente.com/hook')
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Conectar' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Ya los he guardado' }))

    await userEvent.click(await screen.findByRole('button', { name: 'Enviar prueba' }))
    expect(await screen.findByText('El CRM aceptó el evento de prueba.')).toBeInTheDocument()

    const update = vi.spyOn(api, 'updateCrmIntegration')
    await userEvent.click(screen.getByRole('button', { name: 'Desactivar' }))
    await waitFor(() => expect(update).toHaveBeenCalledWith(expect.any(String), { status: 'inactive' }))
    expect(await within(webhookCard()).findByText('Inactivo')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Rotar secretos' }))
    expect(await screen.findByRole('dialog', { name: 'Secretos de la integración' })).toBeInTheDocument()
  })

  it('el gestor del tenant también la gestiona', async () => {
    await open('tenant_manager')
    expect(screen.getByRole('button', { name: 'Conectar' })).toBeInTheDocument()
  })
})
