import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { createMockAdminApi } from '@/core/admin/mockAdminApi'
import { SEED } from '@/test/adminFixtures'
import { fakeAuthApi, makeUser, renderApp } from '@/test/renderApp'

const setup = () => {
  const admin = createMockAdminApi({ latencyMs: 0, seed: SEED })
  renderApp('/plans', fakeAuthApi(makeUser('admin')), admin)
  return admin
}

describe('PlansPage', { timeout: 30_000 }, () => {
  it('solo el admin entra a Planes', async () => {
    renderApp('/plans', fakeAuthApi(makeUser('tenant_manager')))
    expect(await screen.findByRole('heading', { level: 1 }, { timeout: 5000 })).not.toHaveTextContent('Planes')
  })

  it('crea un plan convirtiendo los importes a micro-unidades y valida el código', async () => {
    const admin = setup()
    const create = vi.spyOn(admin, 'createPlan')
    await userEvent.click(await screen.findByRole('button', { name: 'Nuevo plan' }, { timeout: 5000 }))
    const dialog = within(screen.getByRole('dialog'))
    await userEvent.type(dialog.getByLabelText('Nombre'), 'Básico')
    await userEvent.type(dialog.getByLabelText(/Código/), 'mal código')
    await userEvent.type(dialog.getByLabelText('Cuota mensual (€)'), '19,90')
    await userEvent.type(dialog.getByLabelText('Incluidos'), '300')
    await userEvent.type(dialog.getByLabelText('Precio extra (€)'), '0,03')
    await userEvent.click(dialog.getByRole('button', { name: 'Guardar' }))
    expect(dialog.getByText(/Código no válido/)).toBeInTheDocument()
    expect(create).not.toHaveBeenCalled()

    await userEvent.clear(dialog.getByLabelText(/Código/))
    await userEvent.type(dialog.getByLabelText(/Código/), 'basico')
    await userEvent.click(dialog.getByRole('button', { name: 'Guardar' }))

    expect(create).toHaveBeenCalledWith(
      expect.objectContaining({
        code: 'basico',
        monthly_fee_micros: 19_900_000,
        included_messages: { '*': 300 },
        overage_price_micros: { '*': 30_000 },
        margin_pct: '30',
      }),
    )
    expect(await screen.findByRole('heading', { name: /Básico/ })).toBeInTheDocument()
  })

  it('al editar, "Usar sugeridos" copia el coste medio × (1 + margen) al precio extra', async () => {
    const admin = setup()
    const update = vi.spyOn(admin, 'updatePlan')
    await userEvent.click(await screen.findByRole('button', { name: 'Editar Pro' }, { timeout: 5000 }))
    const dialog = within(screen.getByRole('dialog'))
    await userEvent.click(await dialog.findByRole('button', { name: 'Usar sugeridos' }))
    await userEvent.click(dialog.getByRole('button', { name: 'Guardar' }))

    // Pro: margen 35 %; coste medio simulado 0,00115 € (WhatsApp) y 0,00098 € (Telegram).
    expect(update).toHaveBeenCalledWith(
      'plan-pro',
      expect.objectContaining({
        overage_price_micros: expect.objectContaining({ whatsapp_evolution: 1553, telegram: 1323 }),
      }),
    )
  })

  it('no deja borrar un plan con tenants suscritos', async () => {
    setup()
    await userEvent.click(await screen.findByRole('button', { name: 'Eliminar Pro' }, { timeout: 5000 }))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Eliminar plan' }))
    expect(await screen.findByText(/desactívalo en vez de eliminarlo/)).toBeInTheDocument()
  })

  it('en Costes, "Añadir tarifa" sobre un contador sin tarifa lo precarga', async () => {
    const admin = setup()
    const create = vi.spyOn(admin, 'createCostRate')
    await userEvent.click(await screen.findByRole('tab', { name: 'Costes' }, { timeout: 5000 }))
    await userEvent.click(await screen.findByRole('button', { name: 'Añadir tarifa' }))
    const dialog = within(screen.getByRole('dialog'))
    expect(dialog.getByLabelText(/Proveedor/)).toHaveValue('telegram')
    expect(dialog.getByLabelText(/SKU/)).toHaveValue('message.outbound')
    await userEvent.type(dialog.getByLabelText('Precio (€)'), '0')
    await userEvent.click(dialog.getByRole('button', { name: 'Guardar' }))

    expect(create).toHaveBeenCalledWith(
      expect.objectContaining({ kind: 'channel', provider: 'telegram', unit: 'message', price_micros: 0, per_quantity: 1 }),
    )
    expect(await screen.findByText('Todo el consumo reciente tiene tarifa.')).toBeInTheDocument()
  })
})
