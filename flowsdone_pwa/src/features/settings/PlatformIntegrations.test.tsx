import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { AdminApi } from '@/core/admin/AdminApi'
import { createMockAdminApi } from '@/core/admin/mockAdminApi'
import { ApiError } from '@/core/http/apiFetch'
import { SEED } from '@/test/adminFixtures'
import { fakeAuthApi, makeUser, renderApp } from '@/test/renderApp'
import type { Role } from '@/core/auth/types'

const seeded = (over: Partial<AdminApi> = {}): AdminApi => ({ ...createMockAdminApi({ latencyMs: 0, seed: SEED }), ...over })

async function open(role: Role = 'admin', api: AdminApi = seeded()) {
  renderApp('/ajustes', fakeAuthApi(makeUser(role)), api)
  await screen.findByRole('heading', { level: 1, name: 'Ajustes' })
}
const row = (label: string) => screen.getByText(label).closest('li') as HTMLElement

afterEach(() => vi.restoreAllMocks())

describe('visibilidad por perfil', () => {
  it('el admin ve las cuatro integraciones, todas sin configurar', async () => {
    await open('admin')
    expect(await screen.findByText('Integraciones de plataforma')).toBeInTheDocument()
    await screen.findByText('Meta (Facebook + Instagram)') // espera a que carguen las filas
    for (const label of ['Meta (Facebook + Instagram)', 'X (Twitter)', 'TikTok', 'Twilio (voz)']) {
      expect(within(row(label)).getByText('Sin configurar')).toBeInTheDocument()
    }
  })

  it.each(['tenant_manager', 'botmaster', 'client'] as const)('%s no ve la sección ni la pide a la API', async (role) => {
    const list = vi.fn()
    await open(role, seeded({ listChannelApps: list }))
    expect(screen.getByText('Apariencia')).toBeInTheDocument()
    expect(screen.queryByText('Integraciones de plataforma')).not.toBeInTheDocument()
    expect(list).not.toHaveBeenCalled()
  })
})

describe('configurar', () => {
  it('valida los obligatorios y guarda: el proveedor pasa a "Configurada"', async () => {
    await open()
    await userEvent.click(await screen.findByRole('button', { name: 'Configurar X (Twitter)' }))
    const dialog = screen.getByRole('dialog', { name: 'Configurar X (Twitter)' })

    await userEvent.click(within(dialog).getByRole('button', { name: 'Guardar' }))
    expect(within(dialog).getByText('Consumer Secret es obligatorio.')).toBeInTheDocument()

    await userEvent.type(within(dialog).getByLabelText('Consumer Secret'), 'mi-secreto')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Guardar' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    await waitFor(() => expect(within(row('X (Twitter)')).getByText('Configurada')).toBeInTheDocument())
  })

  it('los campos de secretos son de tipo password y el valor nunca vuelve a la pantalla', async () => {
    await open()
    await userEvent.click(await screen.findByRole('button', { name: 'Configurar Twilio (voz)' }))
    const token = screen.getByLabelText('Auth Token')
    expect(token).toHaveAttribute('type', 'password')
    await userEvent.type(token, 'twilio-secreto-123')
    await userEvent.click(screen.getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(within(row('Twilio (voz)')).getByText('Configurada')).toBeInTheDocument())
    expect(document.body.textContent).not.toContain('twilio-secreto-123')
  })

  it('reemplazar avisa que hay que volver a introducir todo, y el error del gateway se muestra', async () => {
    const upsert = vi.fn().mockResolvedValueOnce({}).mockRejectedValueOnce(new ApiError(403, 'forbidden'))
    await open('admin', seeded({ upsertChannelApp: upsert, listChannelApps: vi.fn().mockResolvedValue([{ id: '1', provider: 'tiktok', has_credentials: true, config: {}, status: 'active', created_at: '', updated_at: '' }]) }))
    await userEvent.click(await screen.findByRole('button', { name: 'Reemplazar TikTok' }))
    const dialog = screen.getByRole('dialog', { name: 'Reemplazar credenciales de TikTok' })
    expect(within(dialog).getByText(/no se pueden mostrar/)).toBeInTheDocument()

    await userEvent.type(within(dialog).getByLabelText('Client Secret'), 'x')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())

    await userEvent.click(screen.getByRole('button', { name: 'Reemplazar TikTok' }))
    await userEvent.type(screen.getByLabelText('Client Secret'), 'y')
    await userEvent.click(screen.getByRole('button', { name: 'Guardar' }))
    expect(await screen.findByText(/no tiene permiso/)).toBeInTheDocument()
  })
})

describe('token de verificación de Meta', () => {
  async function configureMeta({ alreadyOpen = false } = {}) {
    if (!alreadyOpen) await open()
    await userEvent.click(await screen.findByRole('button', { name: 'Configurar Meta (Facebook + Instagram)' }))
    await userEvent.type(screen.getByLabelText('App Secret'), 'APP-SECRET-NO-MOSTRAR')
    await userEvent.type(screen.getByLabelText('Token de verificación del webhook'), 'verify-123')
    await userEvent.click(screen.getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(within(row('Meta (Facebook + Instagram)')).getByText('Configurada')).toBeInTheDocument())
  }

  it('solo aparece para Meta ya configurada y muestra únicamente el token, nunca el App Secret', async () => {
    await open()
    await screen.findByText('Meta (Facebook + Instagram)')
    expect(screen.queryByRole('button', { name: /Ver token de verificación/ })).not.toBeInTheDocument()

    await configureMeta({ alreadyOpen: true })
    await userEvent.click(screen.getByRole('button', { name: /Ver token de verificación/ }))
    expect(await screen.findByLabelText('Token de verificación')).toHaveTextContent('verify-123')
    expect(document.body.textContent).not.toContain('APP-SECRET-NO-MOSTRAR')
  })

  it('se oculta solo a los 30 s', async () => {
    const timeouts = vi.spyOn(globalThis, 'setTimeout')
    await configureMeta()
    await userEvent.click(screen.getByRole('button', { name: /Ver token de verificación/ }))
    await screen.findByLabelText('Token de verificación')

    // OJO: React Query también programa un temporizador de 30 s (su staleTime). No se puede
    // asumir cuál es "el nuestro": se disparan todos los de 30 s y debe haberse ocultado.
    const thirtySeconds = timeouts.mock.calls.filter(([, ms]) => ms === 30_000)
    expect(thirtySeconds.length).toBeGreaterThan(0)
    act(() => thirtySeconds.forEach(([callback]) => (callback as () => void)()))
    await waitFor(() => expect(screen.queryByLabelText('Token de verificación')).not.toBeInTheDocument())
  })

  it('"Copiar" envía el token al portapapeles y lo confirma', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    await configureMeta()
    await userEvent.click(screen.getByRole('button', { name: /Ver token de verificación/ }))
    await userEvent.click(await screen.findByRole('button', { name: 'Copiar' }))

    expect(writeText).toHaveBeenCalledWith('verify-123')
    expect(await screen.findByRole('button', { name: 'Copiado' })).toBeInTheDocument()
  })

  it('quitar Meta pide confirmación, la deja sin configurar y oculta el token', async () => {
    await configureMeta()
    await userEvent.click(screen.getByRole('button', { name: /Ver token de verificación/ }))
    await screen.findByLabelText('Token de verificación')

    await userEvent.click(screen.getByRole('button', { name: 'Quitar Meta (Facebook + Instagram)' }))
    const dialog = screen.getByRole('dialog', { name: 'Quitar Meta (Facebook + Instagram)' })
    expect(within(dialog).getByRole('button', { name: 'Cancelar' })).toHaveFocus()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Quitar credenciales' }))

    await waitFor(() => expect(within(row('Meta (Facebook + Instagram)')).getByText('Sin configurar')).toBeInTheDocument())
    expect(screen.queryByLabelText('Token de verificación')).not.toBeInTheDocument()
  })
})

it('si la lista falla ofrece reintentar', async () => {
  const list = vi.fn().mockRejectedValueOnce(new ApiError(400, 'boom')).mockResolvedValue([])
  await open('admin', seeded({ listChannelApps: list }))
  expect(await screen.findByText(/No se pudieron cargar las integraciones: boom/)).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Reintentar' }))
  expect(await screen.findByText('Meta (Facebook + Instagram)')).toBeInTheDocument()
})
