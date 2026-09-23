import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { AdminApi } from '@/core/admin/AdminApi'
import { createMockAdminApi } from '@/core/admin/mockAdminApi'
import type { Role } from '@/core/auth/types'
import { ApiError } from '@/core/http/apiFetch'
import { SEED } from '@/test/adminFixtures'
import { fakeAuthApi, makeUser, renderApp } from '@/test/renderApp'

const api = (over: Partial<AdminApi> = {}): AdminApi => ({ ...createMockAdminApi({ latencyMs: 0, seed: SEED }), ...over })
const LANGFLOW_URL = 'https://agents.example.test/langflow-sso?ticket=abc'
const selectTenant = (id: string) => userEvent.selectOptions(screen.getByRole('combobox', { name: 'Tenant activo' }), id)
const session = (url = LANGFLOW_URL) => vi.fn().mockResolvedValue({ url })
/** The editor lives in its own tab (the "Agents" list opens first). */
const toEditor = async () => userEvent.click(await screen.findByRole('tab', { name: 'Editor de Langflow' }))

async function open(role: Role, adminApi: AdminApi = api()) {
  renderApp('/agents', fakeAuthApi(makeUser(role)), adminApi)
  await screen.findByRole('heading', { level: 1, name: 'Agentes' })
}

describe('editor de Langflow embebido (cualquier staff que pueda editar agentes)', () => {
  // Antes solo el admin lo recibía; tenant_manager/botmaster ahora también
  // (personal de Flowsdone, no de clientes - ver AgentsPage.tsx).
  it.each(['admin', 'tenant_manager'] as const)(
    '%s, con un tenant elegido, ve el editor con la URL de inicio de sesión que da el gateway',
    async (role) => {
      const createLangflowSession = session()
      await open(role, api({ createLangflowSession }))
      await selectTenant('t1')
      await toEditor()
      expect(await screen.findByTitle('Editor de agentes (Langflow)')).toHaveAttribute('src', LANGFLOW_URL)
      expect(createLangflowSession).toHaveBeenCalledWith('t1', undefined)
    },
  )

  it('botmaster (un solo tenant asignado): se auto-selecciona, sin selector que elegir', async () => {
    const createLangflowSession = session()
    await open('botmaster', api({ createLangflowSession }))
    await toEditor()
    expect(await screen.findByTitle('Editor de agentes (Langflow)')).toHaveAttribute('src', LANGFLOW_URL)
    expect(createLangflowSession).toHaveBeenCalledWith('t1', undefined)
    expect(screen.queryByRole('combobox', { name: 'Tenant activo' })).not.toBeInTheDocument()
  })

  it('el botón de pantalla completa entra y sale, y cambia de icono y de etiqueta', async () => {
    await open('admin', api({ createLangflowSession: session() }))
    await selectTenant('t1')
    await toEditor()
    await screen.findByTitle('Editor de agentes (Langflow)')
    const container = screen.getByTitle('Editor de agentes (Langflow)').parentElement as HTMLElement

    expect(document.fullscreenElement).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Ver a pantalla completa' }))
    expect(document.fullscreenElement).toBe(container)

    const exit = await screen.findByRole('button', { name: 'Salir de pantalla completa' })
    await userEvent.click(exit)
    expect(document.fullscreenElement).toBeNull()
    expect(await screen.findByRole('button', { name: 'Ver a pantalla completa' })).toBeInTheDocument()
  })

  it('con "Todos los tenants" pide elegir uno y no abre Langflow', async () => {
    const createLangflowSession = session()
    await open('admin', api({ createLangflowSession }))
    expect(await screen.findByText('Elige un tenant')).toBeInTheDocument()
    expect(document.querySelector('iframe')).toBeNull()
    expect(createLangflowSession).not.toHaveBeenCalled()
  })

  it('al cambiar de tenant pide una sesión nueva y recarga el iframe (el ticket es de un solo uso)', async () => {
    const createLangflowSession = vi
      .fn()
      .mockResolvedValueOnce({ url: 'https://agents.example.test/langflow-sso?ticket=uno' })
      .mockResolvedValueOnce({ url: 'https://agents.example.test/langflow-sso?ticket=dos' })
    await open('admin', api({ createLangflowSession }))
    await selectTenant('t1')
    await toEditor()
    expect(await screen.findByTitle('Editor de agentes (Langflow)')).toHaveAttribute('src', expect.stringContaining('ticket=uno'))
    await selectTenant('t2')
    await waitFor(() =>
      expect(screen.getByTitle('Editor de agentes (Langflow)')).toHaveAttribute('src', expect.stringContaining('ticket=dos')),
    )
    expect(createLangflowSession.mock.calls.map((c) => c[0])).toEqual(['t1', 't2'])
  })

  it('si el gateway falla muestra el error y "Reintentar" pide otra sesión', async () => {
    const createLangflowSession = vi.fn().mockRejectedValueOnce(new ApiError(502, 'langflow unavailable')).mockResolvedValue({ url: LANGFLOW_URL })
    await open('admin', api({ createLangflowSession }))
    await selectTenant('t1')
    await toEditor()
    expect(await screen.findByText(/No se pudo abrir Langflow: langflow unavailable/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Reintentar' }))
    expect(await screen.findByTitle('Editor de agentes (Langflow)')).toBeInTheDocument()
  })

  it('sin Langflow real (modo maqueta) muestra el lienzo de ejemplo', async () => {
    await open('admin')
    await selectTenant('t1')
    await toEditor()
    expect(await screen.findByText(/se embeberá Langflow/)).toBeInTheDocument()
  })
})
