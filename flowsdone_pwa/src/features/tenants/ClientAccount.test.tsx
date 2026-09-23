import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { createMockAdminApi } from '@/core/admin/mockAdminApi'
import { SEED, USERS } from '@/test/adminFixtures'
import { fakeAuthApi, makeUser, renderApp } from '@/test/renderApp'

/** Seed where t1's client account (Carla) is still pending activation. */
const pendingSeed = { ...SEED, users: USERS.map((u) => (u.role === 'client' ? { ...u, status: 'pending' as const, last_login_at: null } : u)) }

const cardOf = async (title: string) => (await screen.findByRole('heading', { level: 3, name: title })).closest('.rounded-card') as HTMLElement

describe('Tenants: cuenta del cliente', { timeout: 20_000 }, () => {
  it('el admin ve la cuenta del cliente y le reenvía la activación', async () => {
    const admin = createMockAdminApi({ latencyMs: 0, seed: pendingSeed })
    const resend = vi.spyOn(admin, 'resendUserActivation')
    renderApp('/tenants', fakeAuthApi(makeUser('admin')), admin)

    const card = await cardOf('Cuenta del cliente')
    expect(await within(card).findByText('Carla Cliente')).toBeInTheDocument()
    expect(within(card).getByText('carla@clinica-vital.com')).toBeInTheDocument()
    expect(within(card).getByText('Pendiente de activar')).toBeInTheDocument()
    expect(within(card).getByText('Todavía no ha entrado en la consola.')).toBeInTheDocument()

    await userEvent.click(within(card).getByRole('button', { name: 'Reenviar email de activación' }))
    expect(resend).toHaveBeenCalledWith('u4')
    expect(await within(card).findByText('Se reenvió el email de activación a carla@clinica-vital.com.')).toBeInTheDocument()
  })

  it('la checklist del alta también permite reenviarla mientras está pendiente', async () => {
    const admin = createMockAdminApi({ latencyMs: 0, seed: pendingSeed })
    const resend = vi.spyOn(admin, 'resendUserActivation')
    renderApp('/tenants', fakeAuthApi(makeUser('admin')), admin)

    const card = await cardOf('Estado del alta')
    await userEvent.click(await within(card).findByRole('button', { name: 'Reenviar email de activación' }))
    expect(resend).toHaveBeenCalledWith('u4')
  })

  it('con la cuenta ya activada no se ofrece reenviar', async () => {
    renderApp('/tenants', fakeAuthApi(makeUser('admin')), createMockAdminApi({ latencyMs: 0, seed: SEED }))
    const card = await cardOf('Cuenta del cliente')
    expect(await within(card).findByText('Activo')).toBeInTheDocument()
    expect(within(card).queryByRole('button', { name: 'Reenviar email de activación' })).not.toBeInTheDocument()
  })

  it('el gestor no ve la cuenta del cliente (listar usuarios es solo de admin)', async () => {
    renderApp('/tenants', fakeAuthApi(makeUser('tenant_manager')), createMockAdminApi({ latencyMs: 0, seed: pendingSeed }))
    expect(await screen.findByRole('heading', { level: 3, name: 'Estado del alta' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { level: 3, name: 'Cuenta del cliente' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Reenviar email de activación' })).not.toBeInTheDocument()
  })
})
