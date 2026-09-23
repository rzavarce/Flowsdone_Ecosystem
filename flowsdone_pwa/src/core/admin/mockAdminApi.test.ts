import { describe, expect, it } from 'vitest'
import { AGENTS, CONNECTIONS, PROJECTS, SEED } from '@/test/adminFixtures'
import { createMockAdminApi } from './mockAdminApi'

const make = () => createMockAdminApi({ latencyMs: 0, seed: SEED })
const input = { project_id: 'p1', agent_id: 'a1', channel_type: 'whatsapp_evolution' as const, external_id: 'nueva-instancia' }

describe('mockAdminApi', () => {
  it('filtra proyectos por tenant y agentes/conexiones por proyecto', async () => {
    const api = make()
    expect((await api.listProjects('t1')).map((p) => p.id)).toEqual(['p1'])
    expect(await api.listProjects()).toHaveLength(PROJECTS.length)
    expect((await api.listAgents('p1')).map((a) => a.id)).toEqual(['a1', 'a1b'])
    expect(await api.listAgents()).toHaveLength(AGENTS.length)
    expect((await api.listChannelConnections('p2')).map((c) => c.id)).toEqual(['c3'])
    expect(await api.listChannelConnections()).toHaveLength(CONNECTIONS.length)
  })

  it('cada instancia parte de datos limpios (no comparten estado)', async () => {
    const a = make()
    await a.createChannelConnection(input)
    expect(await make().listChannelConnections()).toHaveLength(CONNECTIONS.length)
  })

  it('crea una conexión y la lista', async () => {
    const api = make()
    const created = await api.createChannelConnection({ ...input, display_name: 'Mi canal', credentials: { k: 'v' } })
    expect(created).toMatchObject({ project_id: 'p1', display_name: 'Mi canal', status: 'active', has_credentials: true })
    expect((await api.listChannelConnections()).map((c) => c.id)).toContain(created.id)
  })

  it('rechaza un canal duplicado (409) igual que el gateway', async () => {
    const api = make()
    await expect(api.createChannelConnection({ ...input, channel_type: 'telegram', external_id: '123456789:SECRETTOKEN' })).rejects.toMatchObject({ status: 409 })
  })

  it('exige que el agente sea del mismo proyecto, al crear y al editar (400)', async () => {
    const api = make()
    await expect(api.createChannelConnection({ ...input, agent_id: 'a2' })).rejects.toMatchObject({ status: 400 })
    await expect(api.updateChannelConnection('c1', { agent_id: 'a2' })).rejects.toMatchObject({ status: 400 })
    expect((await api.updateChannelConnection('c1', { agent_id: 'a1b' })).agent_id).toBe('a1b')
  })

  it('editar solo cambia lo enviado', async () => {
    const api = make()
    const updated = await api.updateChannelConnection('c1', { status: 'inactive' })
    expect(updated).toMatchObject({ status: 'inactive', display_name: 'WhatsApp Clínica', agent_id: 'a1' })
  })

  it('borrar y editar algo inexistente da 404', async () => {
    const api = make()
    await api.deleteChannelConnection('c1')
    expect(await api.listChannelConnections()).toHaveLength(CONNECTIONS.length - 1)
    await expect(api.deleteChannelConnection('c1')).rejects.toMatchObject({ status: 404 })
    await expect(api.updateChannelConnection('nope', {})).rejects.toMatchObject({ status: 404 })
  })

  it('crear un proyecto rechaza un slug repetido dentro del tenant', async () => {
    const api = make()
    const p = await api.createProject({ tenant_id: 't3', name: 'Nuevo', slug: 'nuevo' })
    expect(p.tenant_id).toBe('t3')
    await expect(api.createProject({ tenant_id: 't3', name: 'Otro', slug: 'nuevo' })).rejects.toMatchObject({ status: 409 })
  })

  it('apps: Meta genera un token de verificación y lo conserva al reemplazar sin enviar uno', async () => {
    const api = make()
    await api.upsertChannelApp('meta', { app_secret: 's1' })
    const first = (await api.revealChannelAppCredentials('meta')).webhook_verify_token
    expect(first).toEqual(expect.any(String))

    await api.upsertChannelApp('meta', { app_secret: 's2' })
    expect((await api.revealChannelAppCredentials('meta')).webhook_verify_token).toBe(first)

    await api.upsertChannelApp('meta', { app_secret: 's3', webhook_verify_token: 'propio' })
    expect((await api.revealChannelAppCredentials('meta')).webhook_verify_token).toBe('propio')
  })

  it('apps: la lista nunca trae secretos, y quitar/revelar una inexistente da 404', async () => {
    const api = make()
    await api.upsertChannelApp('twitter', { consumer_secret: 'secreto' })
    const apps = await api.listChannelApps()
    expect(apps).toEqual([expect.objectContaining({ provider: 'twitter', has_credentials: true })])
    expect(JSON.stringify(apps)).not.toContain('secreto')

    await api.deleteChannelApp('twitter')
    await expect(api.deleteChannelApp('twitter')).rejects.toMatchObject({ status: 404 })
    await expect(api.revealChannelAppCredentials('tiktok')).rejects.toMatchObject({ status: 404 })
  })

  it('tenants: lista, crea, edita y rechaza un slug repetido (409)', async () => {
    const api = make()
    expect((await api.listTenants()).map((t) => t.id)).toEqual(['t1', 't2', 't3'])
    const created = await api.createTenant({ name: 'Nuevo', slug: 'nuevo', client_email: 'c@nuevo.com', client_name: 'Cliente Nuevo' })
    expect(created).toMatchObject({ name: 'Nuevo', slug: 'nuevo', status: 'active' })
    await expect(api.createTenant({ name: 'Otro', slug: 'nuevo', client_email: 'otro@x.com', client_name: 'Otro' })).rejects.toMatchObject({ status: 409 })
    await expect(
      api.createTenant({ name: 'Repetido', slug: 'repetido', client_email: 'c@nuevo.com', client_name: 'Y' }),
    ).rejects.toMatchObject({ status: 409 }) // el email del cliente también es único

    expect((await api.updateTenant(created.id, { name: 'Renombrado', status: 'suspended' }))).toMatchObject({ name: 'Renombrado', status: 'suspended', slug: 'nuevo' })
    await expect(api.updateTenant(created.id, { slug: 'clinica-vital' })).rejects.toMatchObject({ status: 409 })
    await expect(api.updateTenant('nope', {})).rejects.toMatchObject({ status: 404 })
  })

  it('borrar un tenant arrastra en cascada sus proyectos, agentes y canales (como la base de datos)', async () => {
    const api = make()
    await api.deleteTenant('t1')
    expect((await api.listTenants()).map((t) => t.id)).toEqual(['t2', 't3'])
    expect((await api.listProjects()).map((p) => p.id)).toEqual(['p2'])
    expect((await api.listAgents()).map((a) => a.id)).toEqual(['a2'])
    expect((await api.listChannelConnections()).map((c) => c.id)).toEqual(['c3'])
    await expect(api.deleteTenant('t1')).rejects.toMatchObject({ status: 404 })
  })

  it('usuarios: lista, crea pending, edita, borra y reenvía la activación', async () => {
    const api = make()
    const before = await api.listUsers()
    expect(before.length).toBeGreaterThan(0)

    const created = await api.createUser({ email: 'Nuevo@X.com', name: 'Nuevo', role: 'botmaster', tenant_ids: ['t1'] })
    expect(created).toMatchObject({ email: 'nuevo@x.com', role: 'botmaster', status: 'pending', tenant_ids: ['t1'] })
    await expect(api.createUser({ email: 'nuevo@x.com', name: 'Otro', role: 'client', tenant_ids: ['t1'] })).rejects.toMatchObject({ status: 409 })

    const admin = await api.createUser({ email: 'admin2@x.com', name: 'Otro admin', role: 'admin', tenant_ids: ['t1'] })
    expect(admin.tenant_ids).toEqual([]) // admin no lleva tenant_ids aunque se manden

    await api.resendUserActivation(created.id) // sigue pending: no tira
    const updated = await api.updateUser(created.id, { status: 'active' })
    expect(updated.status).toBe('active')
    await expect(api.resendUserActivation(created.id)).rejects.toMatchObject({ status: 404 }) // ya no está pending

    await api.deleteUser(created.id)
    await expect(api.deleteUser(created.id)).rejects.toMatchObject({ status: 404 })
  })

  it('proyectos: editar respeta la unicidad dentro del tenant; borrar arrastra agentes y canales', async () => {
    const api = make()
    const second = await api.createProject({ tenant_id: 't1', name: 'Segundo', slug: 'segundo' })
    await expect(api.updateProject(second.id, { slug: 'atencion' })).rejects.toMatchObject({ status: 409 })
    expect(await api.updateProject(second.id, { name: 'Segundo B', status: 'suspended' })).toMatchObject({ name: 'Segundo B', status: 'suspended' })

    await api.deleteProject('p1')
    expect((await api.listAgents()).map((a) => a.id)).toEqual(['a2'])
    expect((await api.listChannelConnections()).map((c) => c.id)).toEqual(['c3'])
    await expect(api.deleteProject('p1')).rejects.toMatchObject({ status: 404 })
  })

  it('la sesión de Langflow es vacía (maqueta) y falla con un tenant que no existe', async () => {
    const api = make()
    expect(await api.createLangflowSession('t1')).toEqual({ url: '' })
    await expect(api.createLangflowSession('nope')).rejects.toMatchObject({ status: 404 })
  })
})
