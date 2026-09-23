import { describe, expect, it } from 'vitest'
import { can, homePathFor, ROLE_PERMISSIONS } from './permissions'
import { ROLES } from './types'
import { makeUser } from '@/test/renderApp'

describe('can', () => {
  it('niega todo sin usuario', () => {
    expect(can(null, 'settings:view')).toBe(false)
  })

  it('basta con uno de los permisos pedidos', () => {
    expect(can(makeUser('client'), 'dashboard:view', 'reports:view')).toBe(true)
    expect(can(makeUser('client'), 'dashboard:view', 'agents:edit')).toBe(false)
  })

  it('el administrador y el gestor operan todo el producto', () => {
    for (const role of ['admin', 'tenant_manager'] as const) {
      for (const p of ['dashboard:view', 'conversations:manage', 'channels:manage', 'agents:edit'] as const) {
        expect(can(makeUser(role), p)).toBe(true)
      }
    }
  })

  it('el botmaster edita agentes, canales y conversaciones de sus tenants, pero no ve dashboards', () => {
    const u = makeUser('botmaster')
    expect(can(u, 'agents:edit')).toBe(true)
    expect(can(u, 'channels:manage')).toBe(true)
    expect(can(u, 'conversations:manage')).toBe(true)
    expect(can(u, 'dashboard:view', 'reports:view')).toBe(false)
  })

  it('el cliente solo ve reportes', () => {
    const u = makeUser('client')
    expect(can(u, 'reports:view')).toBe(true)
    expect(can(u, 'dashboard:view', 'conversations:manage', 'channels:manage', 'agents:edit')).toBe(false)
  })

  it('todos los perfiles pueden abrir Ajustes (apariencia)', () => {
    for (const role of ROLES) expect(ROLE_PERMISSIONS[role]).toContain('settings:view')
  })
})

describe('homePathFor', () => {
  it.each([
    ['admin', '/dashboard'],
    ['tenant_manager', '/dashboard'],
    ['client', '/dashboard'],
    ['botmaster', '/agents'],
  ] as const)('%s -> %s', (role, path) => {
    expect(homePathFor(makeUser(role))).toBe(path)
  })
})
