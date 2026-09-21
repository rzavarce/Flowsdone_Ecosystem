import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { AdminApi } from '@/core/admin/AdminApi'
import { createMockAdminApi } from '@/core/admin/mockAdminApi'
import type { Role } from '@/core/auth/types'
import { ApiError } from '@/core/http/apiFetch'
import { SEED } from '@/test/adminFixtures'
import { fakeAuthApi, makeUser, renderApp } from '@/test/renderApp'

const api = (over: Partial<AdminApi> = {}): AdminApi => ({ ...createMockAdminApi({ latencyMs: 0, seed: SEED }), ...over })
const LANGFLOW_URL = 'https://agents.example.test/'

async function open(role: Role, adminApi: AdminApi = api()) {
  renderApp('/agentes', fakeAuthApi(makeUser(role)), adminApi)
  await screen.findByRole('heading', { level: 1, name: 'Agentes' })
}

afterEach(() => vi.unstubAllEnvs())

describe('editor de Langflow: solo para el equipo de la plataforma', () => {
  it('el admin ve el editor embebido', async () => {
    vi.stubEnv('VITE_LANGFLOW_URL', LANGFLOW_URL)
    await open('admin')
    expect(screen.getByTitle('Editor de agentes (Langflow)')).toHaveAttribute('src', LANGFLOW_URL)
  })

  it('el admin sin URL configurada ve la maqueta del lienzo', async () => {
    await open('admin')
    expect(screen.getByText(/se embeberá Langflow/)).toBeInTheDocument()
  })

  // Regresión de seguridad: Langflow no separa tenants, quien abre su interfaz ve TODO.
  it.each(['tenant_manager', 'botmaster'] as const)('%s NUNCA recibe el iframe de Langflow, aunque la URL esté configurada', async (role) => {
    vi.stubEnv('VITE_LANGFLOW_URL', LANGFLOW_URL)
    await open(role)
    await screen.findByText(/es solo para el equipo de la plataforma/)
    expect(screen.queryByTitle('Editor de agentes (Langflow)')).not.toBeInTheDocument()
    expect(document.querySelector('iframe')).toBeNull()
    expect(document.body.innerHTML).not.toContain(LANGFLOW_URL)
  })
})

describe('agentes del tenant (gestor y botmaster)', () => {
  it('lista solo los agentes de su tenant activo, sin los de otros tenants', async () => {
    await open('botmaster')
    // t1: Recepción y Citas. "Asesor" es del proyecto de t2.
    expect(await screen.findByRole('heading', { level: 2, name: 'Recepción' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 2, name: 'Citas' })).toBeInTheDocument()
    expect(screen.queryByText('Asesor')).not.toBeInTheDocument()
    expect(screen.getAllByText('Atención')).toHaveLength(2) // el proyecto al que pertenecen
    expect(screen.getByText('Por defecto')).toBeInTheDocument()
  })

  it('el mensaje explica por qué no hay editor y a quién pedirlo', async () => {
    await open('tenant_manager')
    expect(await screen.findByText(/contiene los agentes de todos los clientes/)).toBeInTheDocument()
    expect(screen.getByText('Los agentes de tus tenants.')).toBeInTheDocument()
  })

  it('sin agentes muestra el estado vacío', async () => {
    await open('botmaster', api({ listAgents: vi.fn().mockResolvedValue([]) }))
    expect(await screen.findByText('Aún no hay agentes')).toBeInTheDocument()
  })

  it('si la carga falla muestra el error y "Reintentar" lo vuelve a pedir', async () => {
    const list = vi.fn().mockRejectedValueOnce(new ApiError(400, 'boom')).mockResolvedValue([])
    await open('botmaster', api({ listAgents: list }))
    expect(await screen.findByText(/No se pudieron cargar los agentes: boom/)).toBeInTheDocument()
    screen.getByRole('button', { name: 'Reintentar' }).click()
    await waitFor(() => expect(screen.getByText('Aún no hay agentes')).toBeInTheDocument())
  })
})
