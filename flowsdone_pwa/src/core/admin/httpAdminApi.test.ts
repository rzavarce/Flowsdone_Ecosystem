import { describe, expect, it, vi } from 'vitest'
import { createHttpAdminApi } from './httpAdminApi'

const json = (body: unknown, status = 200) => new Response(status === 204 ? null : JSON.stringify(body), { status })

function setup(body: unknown = [], status = 200) {
  const fetchFn = vi.fn().mockResolvedValue(json(body, status))
  return { api: createHttpAdminApi(fetchFn), fetchFn, call: () => fetchFn.mock.calls[0]! as [string, RequestInit] }
}

describe('httpAdminApi', () => {
  it('lista proyectos: /api/admin/projects, con tenant_id solo si se pide', async () => {
    const a = setup()
    await a.api.listProjects()
    expect(a.call()[0]).toBe('/api/admin/projects')

    const b = setup()
    await b.api.listProjects('t-1')
    expect(b.call()[0]).toBe('/api/admin/projects?tenant_id=t-1')
  })

  it('lista agentes y conexiones, con project_id opcional', async () => {
    const a = setup()
    await a.api.listAgents('p-1')
    expect(a.call()[0]).toBe('/api/admin/agents?project_id=p-1')

    const b = setup()
    await b.api.listChannelConnections()
    expect(b.call()[0]).toBe('/api/admin/channel-connections')
  })

  it('crea un proyecto y una conexión con POST y el cuerpo tal cual', async () => {
    const a = setup({ id: 'p' })
    await a.api.createProject({ tenant_id: 't', name: 'N', slug: 'n' })
    expect(a.call()[0]).toBe('/api/admin/projects')
    expect(a.call()[1].method).toBe('POST')
    expect(JSON.parse(a.call()[1].body as string)).toEqual({ tenant_id: 't', name: 'N', slug: 'n' })

    const b = setup({ id: 'c' })
    const input = { project_id: 'p', agent_id: 'a', channel_type: 'telegram' as const, external_id: 'x', credentials: { k: 'v' } }
    await b.api.createChannelConnection(input)
    expect(b.call()[0]).toBe('/api/admin/channel-connections')
    expect(JSON.parse(b.call()[1].body as string)).toEqual(input)
  })

  it('edita con PATCH y borra con DELETE (204 -> undefined)', async () => {
    const a = setup({ id: 'c' })
    await a.api.updateChannelConnection('c-9', { status: 'inactive' })
    expect(a.call()[0]).toBe('/api/admin/channel-connections/c-9')
    expect(a.call()[1].method).toBe('PATCH')
    expect(JSON.parse(a.call()[1].body as string)).toEqual({ status: 'inactive' })

    const b = setup(undefined, 204)
    await expect(b.api.deleteChannelConnection('c-9')).resolves.toBeUndefined()
    expect(b.call()[1].method).toBe('DELETE')
  })

  it('las apps compartidas: PUT envuelve las credenciales, DELETE y reveal', async () => {
    const a = setup({ provider: 'meta' })
    await a.api.upsertChannelApp('meta', { app_secret: 's' })
    expect(a.call()[0]).toBe('/api/admin/channel-apps/meta')
    expect(a.call()[1].method).toBe('PUT')
    expect(JSON.parse(a.call()[1].body as string)).toEqual({ credentials: { app_secret: 's' } })

    const b = setup(undefined, 204)
    await b.api.deleteChannelApp('meta')
    expect(b.call()[0]).toBe('/api/admin/channel-apps/meta')

    const c = setup({ provider: 'meta', credentials: { webhook_verify_token: 'tok' } })
    expect(await c.api.revealChannelAppCredentials('meta')).toEqual({ webhook_verify_token: 'tok' })
    expect(c.call()[0]).toBe('/api/admin/channel-apps/meta/credentials')
  })
})
