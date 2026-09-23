import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { AdminApi } from '@/core/admin/AdminApi'
import { createMockAdminApi } from '@/core/admin/mockAdminApi'
import { ApiError } from '@/core/http/apiFetch'
import { SEED } from '@/test/adminFixtures'
import { fakeAuthApi, makeUser, renderApp } from '@/test/renderApp'

const seeded = (over: Partial<AdminApi> = {}): AdminApi => ({ ...createMockAdminApi({ latencyMs: 0, seed: SEED }), ...over })

/** Renderiza /channels y espera a que termine la carga inicial. */
async function open(role: 'admin' | 'tenant_manager' = 'admin', api: AdminApi = seeded()) {
  const view = renderApp('/channels', fakeAuthApi(makeUser(role)), api)
  await screen.findByRole('heading', { level: 1, name: 'Canales' })
  return view
}
const names = () => screen.queryAllByRole('heading', { level: 2 }).map((h) => h.textContent)
const selectTenant = (id: string) => userEvent.selectOptions(screen.getByRole('combobox', { name: 'Tenant activo' }), id)

describe('listado', () => {
  it('muestra un spinner mientras carga', () => {
    renderApp('/channels', fakeAuthApi(makeUser('admin')), seeded())
    expect(screen.getByText('Cargando sesión')).toBeInTheDocument()
  })

  it('un admin en "Todos los tenants" ve todo, con el tenant y proyecto de cada canal', async () => {
    await open()
    await waitFor(() => expect(names()).toEqual(['WhatsApp Clínica', 'Bot de citas', 'Instagram Norte']))
    expect(screen.getAllByText('Clínica Vital · Atención', { selector: 'dd' })).toHaveLength(2)
    expect(screen.getByText('Inmobiliaria Norte · Ventas')).toBeInTheDocument()
    expect(screen.getByText('Canales conectados de todos los tenants.')).toBeInTheDocument()
  })

  it('el selector de tenant recorta la lista, y un tenant sin canales muestra el estado vacío', async () => {
    await open()
    await waitFor(() => expect(names()).toHaveLength(3))

    await selectTenant('t1')
    await waitFor(() => expect(names()).toEqual(['WhatsApp Clínica', 'Bot de citas']))
    expect(screen.getByText('Canales conectados de Clínica Vital.')).toBeInTheDocument()

    await selectTenant('t2')
    await waitFor(() => expect(names()).toEqual(['Instagram Norte']))

    await selectTenant('t3')
    expect(await screen.findByText('Aún no hay canales conectados')).toBeInTheDocument()
  })

  it('un gestor ve solo su tenant activo', async () => {
    await open('tenant_manager')
    await waitFor(() => expect(names()).toEqual(['WhatsApp Clínica', 'Bot de citas']))
    // Con un tenant activo no hace falta repetir el tenant en la etiqueta del proyecto.
    expect(screen.getAllByText('Atención', { selector: 'dd' })).toHaveLength(2)
  })

  it('nunca pinta el token completo de Telegram (es un secreto)', async () => {
    await open()
    await screen.findByText('Bot de citas')
    expect(screen.getByText('123456789:••••••••')).toBeInTheDocument()
    expect(document.body.textContent).not.toContain('SECRETTOKEN')
  })

  it('marca el estado de cada canal', async () => {
    await open()
    await screen.findByText('Instagram Norte')
    expect(screen.getAllByText('Activo')).toHaveLength(2)
    expect(screen.getByText('Inactivo')).toBeInTheDocument()
  })

  it('si la carga falla muestra el error y "Reintentar" vuelve a pedir los datos', async () => {
    // 400: los errores 4xx no se reintentan solos (los 5xx sí, con espera), así el fallo se ve enseguida.
    const list = vi.fn().mockRejectedValueOnce(new ApiError(400, 'boom')).mockResolvedValue([])
    await open('admin', seeded({ listChannelConnections: list }))
    expect(await screen.findByText(/No se pudieron cargar los canales: boom/)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Reintentar' }))
    expect(await screen.findByText('Aún no hay canales conectados')).toBeInTheDocument()
  })

  it('un 401 (sesión vencida) cierra la sesión y lleva al login', async () => {
    renderApp('/channels', fakeAuthApi(makeUser('admin')), seeded({ listProjects: vi.fn().mockRejectedValue(new ApiError(401, 'not authenticated')) }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Inicia sesión' })).toBeInTheDocument()
  })
})

describe('conectar un canal', () => {
  async function openCreate(role: 'admin' | 'tenant_manager' = 'tenant_manager', api?: AdminApi) {
    await open(role, api)
    await screen.findByText('WhatsApp Clínica')
    await userEvent.click(screen.getByRole('button', { name: /Nuevo canal/ }))
    return screen.getByRole('dialog', { name: 'Conectar un canal' })
  }

  it('preselecciona el proyecto y el agente por defecto, y crea el canal', async () => {
    const dialog = await openCreate()
    expect(within(dialog).getByLabelText('Proyecto')).toHaveValue('p1')
    expect(within(dialog).getByLabelText('Agente')).toHaveValue('a1')
    expect(within(dialog).getByRole('option', { name: 'Recepción (por defecto)' })).toBeInTheDocument()

    await userEvent.type(within(dialog).getByLabelText('Nombre de la instancia'), 'nueva-instancia')
    await userEvent.type(within(dialog).getByLabelText('Nombre para mostrar'), 'WhatsApp Ventas')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Conectar canal' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(await screen.findByText('WhatsApp Ventas')).toBeInTheDocument()
  })

  it('valida los campos obligatorios sin llamar a la API', async () => {
    const create = vi.fn()
    const dialog = await openCreate('tenant_manager', seeded({ createChannelConnection: create }))
    await userEvent.click(within(dialog).getByRole('button', { name: 'Conectar canal' }))

    expect(within(dialog).getByText('Nombre de la instancia es obligatorio.')).toBeInTheDocument()
    expect(create).not.toHaveBeenCalled()
  })

  it('Facebook exige el token de la página y cambia las etiquetas según el canal', async () => {
    const create = vi.fn()
    const dialog = await openCreate('tenant_manager', seeded({ createChannelConnection: create }))
    await userEvent.selectOptions(within(dialog).getByLabelText('Canal'), 'facebook')

    expect(within(dialog).getByLabelText('ID de la página')).toBeInTheDocument()
    expect(within(dialog).getByText(/suscribe la página a la app de Meta/)).toBeInTheDocument()

    await userEvent.type(within(dialog).getByLabelText('ID de la página'), '999')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Conectar canal' }))
    expect(within(dialog).getByText('Token de acceso de la página es obligatorio.')).toBeInTheDocument()
    expect(create).not.toHaveBeenCalled()

    await userEvent.type(within(dialog).getByLabelText('Token de acceso de la página'), 'EAAB-token')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Conectar canal' }))
    await waitFor(() => expect(create).toHaveBeenCalledWith(expect.objectContaining({
      channel_type: 'facebook', external_id: '999', credentials: { page_access_token: 'EAAB-token' },
    })))
  })

  it('los agentes ofrecidos son los del proyecto elegido', async () => {
    const dialog = await openCreate('admin')
    expect(within(dialog).getAllByRole('option').map((o) => o.textContent)).toContain('Recepción (por defecto)')

    await userEvent.selectOptions(within(dialog).getByLabelText('Proyecto'), 'p2')
    await waitFor(() => expect(within(dialog).getByLabelText('Agente')).toHaveValue('a2'))
    expect(within(dialog).queryByRole('option', { name: 'Citas' })).not.toBeInTheDocument()
  })

  it('un canal duplicado muestra el error y deja el diálogo abierto', async () => {
    const dialog = await openCreate()
    await userEvent.selectOptions(within(dialog).getByLabelText('Canal'), 'telegram')
    await userEvent.type(within(dialog).getByLabelText('Token del bot'), '123456789:SECRETTOKEN')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Conectar canal' }))

    expect(await within(dialog).findByText(/Ya existe un elemento con esos datos/)).toBeInTheDocument()
    expect(screen.getByRole('dialog', { name: 'Conectar un canal' })).toBeInTheDocument()
  })

  it('un rechazo de la plataforma (502) se explica con su motivo', async () => {
    const create = vi.fn().mockRejectedValue(new ApiError(502, 'webhook registration failed: Unauthorized'))
    const dialog = await openCreate('tenant_manager', seeded({ createChannelConnection: create }))
    await userEvent.selectOptions(within(dialog).getByLabelText('Canal'), 'telegram')
    await userEvent.type(within(dialog).getByLabelText('Token del bot'), 'mal-token')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Conectar canal' }))
    expect(await within(dialog).findByText(/paso externo falló: Unauthorized/)).toBeInTheDocument()
  })

  it('en un tenant sin proyectos ofrece crear el primero y luego avisa que faltan agentes', async () => {
    await open()
    await selectTenant('t3')
    await userEvent.click(await screen.findByRole('button', { name: /Nuevo canal/ }))
    const dialog = await screen.findByRole('dialog', { name: 'Conectar un canal' })

    const form = within(dialog).getByRole('form', { name: 'Nuevo proyecto' })
    await userEvent.type(within(form).getByLabelText('Nombre del proyecto'), 'Soporte técnico')
    expect(within(form).getByLabelText('Identificador (slug)')).toHaveValue('soporte-tecnico') // slug derivado
    await userEvent.click(within(form).getByRole('button', { name: 'Crear proyecto' }))

    // Ya hay proyecto: aparece el formulario del canal, pero el proyecto aún no tiene agentes.
    expect(await within(dialog).findByLabelText('Proyecto')).toHaveDisplayValue('Soporte técnico')
    expect(within(dialog).getByText(/todavía no tiene agentes/)).toBeInTheDocument()
    expect(within(dialog).getByRole('link', { name: 'Agentes' })).toHaveAttribute('href', '/agents')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Conectar canal' }))
    expect(within(dialog).getByText('Elige un agente.')).toBeInTheDocument()
  })
})

describe('editar un canal', () => {
  it('cambia nombre y estado; no permite cambiar el identificador ni el proyecto', async () => {
    await open('tenant_manager')
    await userEvent.click(await screen.findByRole('button', { name: 'Editar Bot de citas' }))
    const dialog = screen.getByRole('dialog', { name: 'Editar canal' })

    // El token de Telegram nunca aparece completo, tampoco acá.
    expect(within(dialog).getByText('Telegram · 123456789:••••••••')).toBeInTheDocument()
    expect(within(dialog).queryByLabelText('Token del bot')).not.toBeInTheDocument()
    expect(within(dialog).queryByLabelText('Proyecto')).not.toBeInTheDocument()

    const name = within(dialog).getByLabelText('Nombre para mostrar')
    await userEvent.clear(name)
    await userEvent.type(name, 'Citas Telegram')
    await userEvent.selectOptions(within(dialog).getByLabelText('Estado'), 'inactive')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Guardar cambios' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(await screen.findByText('Citas Telegram')).toBeInTheDocument()
    expect(screen.getByText('Inactivo')).toBeInTheDocument()
  })

  it('solo envía las credenciales si se escribieron (vacío = conservar)', async () => {
    const update = vi.fn().mockResolvedValue({})
    await open('admin', seeded({ updateChannelConnection: update }))
    await userEvent.click(await screen.findByRole('button', { name: 'Editar Instagram Norte' }))
    const dialog = screen.getByRole('dialog', { name: 'Editar canal' })

    await userEvent.click(within(dialog).getByRole('button', { name: 'Guardar cambios' }))
    await waitFor(() => expect(update).toHaveBeenCalledTimes(1))
    expect(update.mock.calls[0]![1]).not.toHaveProperty('credentials')

    await userEvent.click(await screen.findByRole('button', { name: 'Editar Instagram Norte' }))
    await userEvent.type(within(screen.getByRole('dialog')).getByLabelText('Token de acceso de la página'), 'nuevo')
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Guardar cambios' }))
    await waitFor(() => expect(update).toHaveBeenCalledTimes(2))
    expect(update.mock.calls[1]![1]).toMatchObject({ credentials: { page_access_token: 'nuevo' } })
  })
})

describe('eliminar un canal', () => {
  it('pide confirmación (foco en Cancelar) y no borra si se cancela', async () => {
    await open('tenant_manager')
    await userEvent.click(await screen.findByRole('button', { name: 'Eliminar WhatsApp Clínica' }))
    const dialog = screen.getByRole('dialog', { name: 'Eliminar WhatsApp Clínica' })
    expect(within(dialog).getByRole('button', { name: 'Cancelar' })).toHaveFocus()

    await userEvent.click(within(dialog).getByRole('button', { name: 'Cancelar' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByText('WhatsApp Clínica')).toBeInTheDocument()
  })

  it('al confirmar borra el canal de la lista', async () => {
    await open('tenant_manager')
    await userEvent.click(await screen.findByRole('button', { name: 'Eliminar WhatsApp Clínica' }))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Eliminar canal' }))

    await waitFor(() => expect(screen.queryByText('WhatsApp Clínica')).not.toBeInTheDocument())
    expect(screen.getByText('Bot de citas')).toBeInTheDocument()
  })

  it('si el borrado falla, muestra el error y mantiene el diálogo', async () => {
    const del = vi.fn().mockRejectedValue(new ApiError(404, 'channel_connection not found'))
    await open('tenant_manager', seeded({ deleteChannelConnection: del }))
    await userEvent.click(await screen.findByRole('button', { name: 'Eliminar WhatsApp Clínica' }))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Eliminar canal' }))

    expect(await screen.findByText(/ya no existe o no tienes acceso/)).toBeInTheDocument()
    expect(screen.getByRole('dialog', { name: 'Eliminar WhatsApp Clínica' })).toBeInTheDocument()
  })
})
