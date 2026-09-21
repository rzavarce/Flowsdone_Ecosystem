import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { AdminApi } from '@/core/admin/AdminApi'
import { createMockAdminApi } from '@/core/admin/mockAdminApi'
import type { AuthApi } from '@/core/auth/AuthApi'
import { ApiError } from '@/core/http/apiFetch'
import { SEED, TENANTS } from '@/test/adminFixtures'
import { fakeAuthApi, makeUser, renderApp } from '@/test/renderApp'
import type { Role } from '@/core/auth/types'

/** Datos de partida; para el gestor el gateway solo devuelve sus tenants (t1, t2). */
const seedFor = (role: Role) => ({ ...SEED, tenants: role === 'admin' ? TENANTS : TENANTS.filter((t) => t.id !== 't3') })
const mock = (role: Role = 'admin') => createMockAdminApi({ latencyMs: 0, seed: seedFor(role) })

async function open(role: Role = 'admin', api: AdminApi = mock(role), auth: AuthApi = fakeAuthApi(makeUser(role))) {
  renderApp('/tenants', auth, api)
  await screen.findByRole('heading', { level: 1, name: 'Tenants' })
  await screen.findByRole('list', { name: 'Tenants' })
  return api
}
const tenantButton = (name: RegExp | string) => within(screen.getByRole('list', { name: 'Tenants' })).getByRole('button', { name })

describe('lista y detalle', () => {
  it('lista los tenants con su slug, su contenido y su estado', async () => {
    await open()
    const list = within(screen.getByRole('list', { name: 'Tenants' }))
    expect(list.getAllByRole('button')).toHaveLength(3)
    expect(tenantButton(/Clínica Vital/)).toHaveTextContent('clinica-vital')
    expect(tenantButton(/Clínica Vital/)).toHaveTextContent('1 proyecto · 2 agentes · 2 canales')
    expect(tenantButton(/Inmobiliaria Norte/)).toHaveTextContent('1 proyecto · 1 agente · 1 canal')
    expect(tenantButton(/Tienda Aurora/)).toHaveTextContent('0 proyectos · 0 agentes · 0 canales')
    expect(tenantButton(/Tienda Aurora/)).toHaveTextContent('Suspendido')
  })

  it('selecciona el primero por defecto y cambia el detalle y los proyectos al elegir otro', async () => {
    await open()
    expect(tenantButton(/Clínica Vital/)).toHaveAttribute('aria-current', 'true')
    expect(screen.getByRole('heading', { level: 2, name: /Clínica Vital/ })).toBeInTheDocument()
    expect(screen.getByText('atencion', { selector: 'p' })).toBeInTheDocument()

    await userEvent.click(tenantButton(/Inmobiliaria Norte/))
    expect(await screen.findByRole('heading', { level: 2, name: /Inmobiliaria Norte/ })).toBeInTheDocument()
    expect(screen.getByText('ventas', { selector: 'p' })).toBeInTheDocument()
    expect(screen.queryByText('atencion', { selector: 'p' })).not.toBeInTheDocument()
  })

  it('un tenant suspendido lo explica y sin proyectos ofrece crear el primero', async () => {
    await open()
    await userEvent.click(tenantButton(/Tienda Aurora/))
    expect(await screen.findByText(/sus canales no responden mensajes/)).toBeInTheDocument()
    expect(screen.getByText('Este tenant aún no tiene proyectos')).toBeInTheDocument()
  })

  it('si la carga falla muestra el error y "Reintentar" lo vuelve a pedir', async () => {
    const list = vi.fn().mockRejectedValueOnce(new ApiError(400, 'boom')).mockResolvedValue(TENANTS)
    renderApp('/tenants', fakeAuthApi(makeUser('admin')), { ...mock(), listTenants: list })
    expect(await screen.findByText(/No se pudieron cargar los tenants: boom/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Reintentar' }))
    expect(await screen.findByRole('list', { name: 'Tenants' })).toBeInTheDocument()
  })

  it('sin tenants muestra el estado vacío (el admin puede crear el primero)', async () => {
    renderApp('/tenants', fakeAuthApi(makeUser('admin')), createMockAdminApi({ latencyMs: 0, seed: { tenants: [], projects: [], agents: [], connections: [] } }))
    expect(await screen.findByText('Aún no hay tenants')).toBeInTheDocument()
    expect(screen.getByText(/Crea el primero/)).toBeInTheDocument()
  })
})

describe('gestión de tenants (admin)', () => {
  it('crea un tenant: el slug sale del nombre, queda seleccionado y avisa a la sesión', async () => {
    const restore = vi.fn()
    const user = makeUser('admin')
    await open('admin', mock(), { restore: async () => (restore(), user), login: async () => user, logout: async () => {} })
    const before = restore.mock.calls.length

    await userEvent.click(screen.getByRole('button', { name: /Nuevo tenant/ }))
    const dialog = screen.getByRole('dialog', { name: 'Nuevo tenant' })
    await userEvent.type(within(dialog).getByLabelText('Nombre'), 'Óptica Ñandú')
    expect(within(dialog).getByLabelText(/Identificador/)).toHaveValue('optica-nandu')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Crear tenant' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(await screen.findByRole('heading', { level: 2, name: /Óptica Ñandú/ })).toBeInTheDocument()
    expect(tenantButton(/Óptica Ñandú/)).toHaveAttribute('aria-current', 'true')
    // El selector de tenant de la sesión sale de /auth/me: hay que volver a pedirlo.
    await waitFor(() => expect(restore.mock.calls.length).toBeGreaterThan(before))
  })

  it('valida los campos y avisa de un slug repetido', async () => {
    await open()
    await userEvent.click(screen.getByRole('button', { name: /Nuevo tenant/ }))
    const dialog = screen.getByRole('dialog', { name: 'Nuevo tenant' })
    await userEvent.click(within(dialog).getByRole('button', { name: 'Crear tenant' }))
    expect(within(dialog).getByText('El nombre es obligatorio.')).toBeInTheDocument()

    await userEvent.type(within(dialog).getByLabelText('Nombre'), 'Clínica Vital')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Crear tenant' }))
    expect(await within(dialog).findByText(/Ya existe un elemento con esos datos/)).toBeInTheDocument()
    expect(screen.getByRole('dialog', { name: 'Nuevo tenant' })).toBeInTheDocument()
  })

  it('edita el nombre de un tenant', async () => {
    await open()
    await userEvent.click(screen.getByRole('button', { name: 'Editar Clínica Vital' }))
    const dialog = screen.getByRole('dialog', { name: 'Editar tenant' })
    const name = within(dialog).getByLabelText('Nombre')
    await userEvent.clear(name)
    await userEvent.type(name, 'Clínica Vital Norte')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Guardar cambios' }))
    expect(await screen.findByRole('heading', { level: 2, name: /Clínica Vital Norte/ })).toBeInTheDocument()
  })

  it('suspender pide confirmación y el tenant queda suspendido; reactivar es inmediato', async () => {
    await open()
    await userEvent.click(screen.getByRole('button', { name: 'Suspender Clínica Vital' }))
    const dialog = screen.getByRole('dialog', { name: 'Suspender Clínica Vital' })
    expect(within(dialog).getByText(/dejarán de responder mensajes/)).toBeInTheDocument()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Suspender tenant' }))

    expect(await screen.findByText(/sus canales no responden mensajes/)).toBeInTheDocument()
    expect(tenantButton(/Clínica Vital/)).toHaveTextContent('Suspendido')

    await userEvent.click(screen.getByRole('button', { name: 'Reactivar Clínica Vital' }))
    await waitFor(() => expect(screen.queryByText(/sus canales no responden mensajes/)).not.toBeInTheDocument())
    expect(tenantButton(/Clínica Vital/)).not.toHaveTextContent('Suspendido')
  })

  it('borrar exige escribir el slug, avisa de la cascada y elimina todo lo que colgaba', async () => {
    const api = await open()
    await userEvent.click(screen.getByRole('button', { name: 'Eliminar Clínica Vital' }))
    const dialog = screen.getByRole('dialog', { name: 'Eliminar Clínica Vital' })
    expect(within(dialog).getByText(/1 proyecto · 2 agentes · 2 canales/)).toBeInTheDocument()
    expect(within(dialog).getByRole('button', { name: 'Cancelar' })).toHaveFocus()

    const confirm = within(dialog).getByRole('button', { name: 'Eliminar tenant' })
    expect(confirm).toBeDisabled()
    await userEvent.type(within(dialog).getByLabelText('Escribe "clinica-vital" para confirmar'), 'clinica')
    expect(confirm).toBeDisabled() // a medias no basta
    await userEvent.type(within(dialog).getByLabelText(/Escribe "clinica-vital"/), '-vital')
    expect(confirm).toBeEnabled()
    await userEvent.click(confirm)

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    await waitFor(() => expect(within(screen.getByRole('list', { name: 'Tenants' })).queryByText('Clínica Vital')).not.toBeInTheDocument())
    // La cascada llegó hasta los proyectos, agentes y canales.
    expect((await api.listProjects()).map((p) => p.id)).toEqual(['p2'])
    expect((await api.listAgents()).map((a) => a.id)).toEqual(['a2'])
    expect((await api.listChannelConnections()).map((c) => c.id)).toEqual(['c3'])
    // La selección pasa a otro tenant existente.
    expect(tenantButton(/Inmobiliaria Norte/)).toHaveAttribute('aria-current', 'true')
  })

  it('el aviso de cascada cuenta lo que hay AHORA, no lo que había en la caché', async () => {
    const api = await open()
    expect(tenantButton(/Clínica Vital/)).toHaveTextContent('1 proyecto · 2 agentes · 2 canales')

    // Alguien (otra pestaña, otra persona) añade contenido después de que se cargó la pantalla.
    const agent = await api.createChannelConnection({ project_id: 'p1', agent_id: 'a1', channel_type: 'whatsapp_evolution', external_id: 'nuevo-canal' })
    expect(agent.id).toBeTruthy()

    await userEvent.click(screen.getByRole('button', { name: 'Eliminar Clínica Vital' }))
    const dialog = await screen.findByRole('dialog', { name: 'Eliminar Clínica Vital' })
    expect(within(dialog).getByText(/1 proyecto · 2 agentes · 3 canales/)).toBeInTheDocument()
  })

  it('cancelar el borrado no toca nada y un fallo se muestra en el diálogo', async () => {
    const del = vi.fn().mockRejectedValue(new ApiError(403, 'forbidden'))
    await open('admin', { ...mock(), deleteTenant: del })
    await userEvent.click(screen.getByRole('button', { name: 'Eliminar Clínica Vital' }))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Cancelar' }))
    expect(del).not.toHaveBeenCalled()

    await userEvent.click(screen.getByRole('button', { name: 'Eliminar Clínica Vital' }))
    const dialog = screen.getByRole('dialog')
    await userEvent.type(within(dialog).getByLabelText(/Escribe "clinica-vital"/), 'clinica-vital')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Eliminar tenant' }))
    expect(await within(dialog).findByText(/no tiene permiso/)).toBeInTheDocument()
    expect(tenantButton(/Clínica Vital/)).toBeInTheDocument()
  })
})

describe('proyectos', () => {
  it('crea un proyecto en el tenant seleccionado (slug derivado del nombre)', async () => {
    await open()
    await userEvent.click(screen.getByRole('button', { name: /Nuevo proyecto/ }))
    const dialog = screen.getByRole('dialog', { name: 'Nuevo proyecto' })
    expect(within(dialog).getByText('Tenant: Clínica Vital')).toBeInTheDocument()
    await userEvent.type(within(dialog).getByLabelText('Nombre'), 'Soporte técnico')
    expect(within(dialog).getByLabelText(/Identificador/)).toHaveValue('soporte-tecnico')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Crear proyecto' }))

    expect(await screen.findByText('soporte-tecnico', { selector: 'p' })).toBeInTheDocument()
    expect(tenantButton(/Clínica Vital/)).toHaveTextContent('2 proyectos')
  })

  it('un slug repetido dentro del tenant muestra el error', async () => {
    await open()
    await userEvent.click(screen.getByRole('button', { name: /Nuevo proyecto/ }))
    const dialog = screen.getByRole('dialog', { name: 'Nuevo proyecto' })
    await userEvent.type(within(dialog).getByLabelText('Nombre'), 'Atención')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Crear proyecto' }))
    expect(await within(dialog).findByText(/Ya existe un elemento/)).toBeInTheDocument()
  })

  it('edita, suspende y reactiva un proyecto', async () => {
    await open()
    await userEvent.click(screen.getByRole('button', { name: 'Editar Atención' }))
    const name = within(screen.getByRole('dialog', { name: 'Editar proyecto' })).getByLabelText('Nombre')
    await userEvent.clear(name)
    await userEvent.type(name, 'Atención 24h')
    await userEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }))
    expect(await screen.findByRole('button', { name: 'Editar Atención 24h' })).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Suspender Atención 24h' }))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Suspender proyecto' }))
    expect(await screen.findByRole('button', { name: 'Reactivar Atención 24h' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Reactivar Atención 24h' }))
    expect(await screen.findByRole('button', { name: 'Suspender Atención 24h' })).toBeInTheDocument()
  })

  it('borrar un proyecto con contenido exige el slug; uno vacío se borra sin escribir nada', async () => {
    const api = await open()
    await userEvent.click(screen.getByRole('button', { name: 'Eliminar Atención' }))
    const dialog = screen.getByRole('dialog', { name: 'Eliminar Atención' })
    expect(within(dialog).getByText(/2 agentes · 2 canales/)).toBeInTheDocument()
    expect(within(dialog).getByRole('button', { name: 'Eliminar proyecto' })).toBeDisabled()
    await userEvent.type(within(dialog).getByLabelText(/Escribe "atencion"/), 'atencion')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Eliminar proyecto' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect((await api.listProjects()).map((p) => p.id)).toEqual(['p2'])
    expect((await api.listChannelConnections()).map((c) => c.id)).toEqual(['c3']) // la cascada llegó a los canales

    // Un proyecto sin agentes ni canales se borra sin pedir el slug.
    await userEvent.click(tenantButton(/Inmobiliaria Norte/))
    await userEvent.click(await screen.findByRole('button', { name: /Nuevo proyecto/ }))
    await userEvent.type(within(screen.getByRole('dialog', { name: 'Nuevo proyecto' })).getByLabelText('Nombre'), 'Vacío')
    await userEvent.click(screen.getByRole('button', { name: 'Crear proyecto' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Eliminar Vacío' }))
    const d2 = screen.getByRole('dialog', { name: 'Eliminar Vacío' })
    expect(within(d2).queryByLabelText(/Escribe/)).not.toBeInTheDocument()
    await userEvent.click(within(d2).getByRole('button', { name: 'Eliminar proyecto' }))
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Eliminar Vacío' })).not.toBeInTheDocument())
  })
})

describe('gestor de tenant', () => {
  it('ve solo sus tenants y puede gestionar proyectos, pero no los tenants', async () => {
    await open('tenant_manager')
    expect(within(screen.getByRole('list', { name: 'Tenants' })).getAllByRole('button')).toHaveLength(2)
    expect(screen.getByText('Tus organizaciones y sus proyectos.')).toBeInTheDocument()

    expect(screen.queryByRole('button', { name: /Nuevo tenant/ })).not.toBeInTheDocument()
    for (const label of ['Editar Clínica Vital', 'Suspender Clínica Vital', 'Eliminar Clínica Vital']) {
      expect(screen.queryByRole('button', { name: label })).not.toBeInTheDocument()
    }
    // Sí gestiona los proyectos.
    expect(screen.getByRole('button', { name: /Nuevo proyecto/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Editar Atención' })).toBeInTheDocument()
  })

  it('arranca en el tenant activo del selector superior', async () => {
    await open('tenant_manager')
    // El gestor de prueba tiene t1 y t2; el activo por defecto es el primero.
    expect(tenantButton(/Clínica Vital/)).toHaveAttribute('aria-current', 'true')
  })
})
