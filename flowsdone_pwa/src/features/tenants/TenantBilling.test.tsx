import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { createMockAdminApi } from '@/core/admin/mockAdminApi'
import { SEED } from '@/test/adminFixtures'
import { fakeAuthApi, makeUser, renderApp } from '@/test/renderApp'

describe('Tenants: plan y consumo', { timeout: 20_000 }, () => {
  it('el admin ve el plan del tenant y puede cambiarlo', async () => {
    const admin = createMockAdminApi({ latencyMs: 0, seed: SEED })
    const put = vi.spyOn(admin, 'putSubscription')
    renderApp('/tenants', fakeAuthApi(makeUser('admin')), admin)

    expect(await screen.findByText('Pro', undefined, { timeout: 5000 })).toBeInTheDocument()
    expect(await screen.findByText(/Tope de gasto de excedente/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Cambiar' }))
    const dialog = within(screen.getByRole('dialog'))
    await userEvent.selectOptions(dialog.getByLabelText('Plan'), 'plan-starter')
    await userEvent.selectOptions(dialog.getByLabelText('Al superar lo incluido'), 'hard_stop')
    await userEvent.click(dialog.getByRole('button', { name: 'Guardar' }))

    expect(put).toHaveBeenCalledWith('t1', { plan_id: 'plan-starter', overage_mode: 'hard_stop', spending_cap_micros: 50_000_000 })
    expect(await screen.findByText('Starter')).toBeInTheDocument()
  })

  it('el consumo del mes muestra los mensajes por canal y el margen para el admin', async () => {
    renderApp('/tenants', fakeAuthApi(makeUser('admin')), createMockAdminApi({ latencyMs: 0, seed: SEED }))
    expect(await screen.findByRole('progressbar', { name: 'WhatsApp' }, { timeout: 5000 })).toBeInTheDocument()
    expect(screen.getByText('Total estimado del mes')).toBeInTheDocument()
    expect(screen.getByText('Margen')).toBeInTheDocument()
  })

  it('el gestor ve el plan pero no puede cambiarlo', async () => {
    renderApp('/tenants', fakeAuthApi(makeUser('tenant_manager')), createMockAdminApi({ latencyMs: 0, seed: SEED }))
    expect(await screen.findByText('Pro', undefined, { timeout: 5000 })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Cambiar' })).not.toBeInTheDocument()
  })
})
