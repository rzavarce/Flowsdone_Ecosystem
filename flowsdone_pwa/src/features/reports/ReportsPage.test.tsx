import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { fakeAuthApi, makeUser, renderApp } from '@/test/renderApp'

const h1 = (name: string) => screen.findByRole('heading', { level: 1, name })

describe('Reportes', () => {
  it('muestra una pestaña por reporte y abre el primero con el tenant activo', async () => {
    renderApp('/reports', fakeAuthApi(makeUser('client')))
    expect(await h1('Reportes')).toBeInTheDocument()
    const tabs = within(await screen.findByRole('tablist', { name: 'Reportes' })).getAllByRole('tab')
    expect(tabs.map((t) => t.textContent)).toEqual(['Canales', 'Agentes', 'Contactos', 'Horarios', 'Consumo'])
    expect(tabs[0]).toHaveAttribute('aria-selected', 'true')
    expect(await screen.findByTitle('Canales')).toHaveAttribute('src', 'about:blank#report_channels&tenant=t1')
  })

  it('al cambiar de pestaña carga ese reporte (y la pestaña queda en la URL)', async () => {
    renderApp('/reports?r=report_usage', fakeAuthApi(makeUser('tenant_manager')))
    expect(await screen.findByRole('tab', { name: 'Consumo', selected: true })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('tab', { name: 'Horarios' }))
    expect(await screen.findByTitle('Horarios')).toHaveAttribute('src', expect.stringContaining('report_hours'))
  })

  it('el botmaster no tiene Reportes', async () => {
    renderApp('/reports', fakeAuthApi(makeUser('botmaster')))
    expect(await screen.findByRole('heading', { level: 1, name: /acceso|permiso/i })).toBeInTheDocument()
  })
})
