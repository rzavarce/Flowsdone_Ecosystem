import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { AuthProvider } from '@/core/auth/AuthProvider'
import type { Role } from '@/core/auth/types'
import { fakeAuthApi, makeUser } from '@/test/renderApp'
import { TenantProvider } from './TenantProvider'
import { useTenant } from './useTenant'

function Probe() {
  const { selectedId, current, canSelectAll, tenants, select } = useTenant()
  return (
    <div>
      <span data-testid="t">{`${selectedId}|${current?.name ?? 'todos'}|${canSelectAll}|${tenants.length}`}</span>
      <button onClick={() => select('t2')}>t2</button>
      <button onClick={() => select('t3')}>t3</button>
    </div>
  )
}

const setup = (role: Role) =>
  render(
    <AuthProvider api={fakeAuthApi(makeUser(role))}>
      <TenantProvider>
        <Probe />
      </TenantProvider>
    </AuthProvider>,
  )

describe('TenantProvider', () => {
  it('el administrador arranca viendo todos los tenants', async () => {
    setup('admin')
    await waitFor(() => expect(screen.getByTestId('t')).toHaveTextContent('all|todos|true|3'))
  })

  it('el gestor arranca en su primer tenant y no puede elegir "todos"', async () => {
    setup('tenant_manager')
    await waitFor(() => expect(screen.getByTestId('t')).toHaveTextContent('t1|Clínica Vital|false|2'))
  })

  it('permite cambiar entre los tenants propios', async () => {
    setup('tenant_manager')
    await waitFor(() => expect(screen.getByTestId('t')).toHaveTextContent('t1'))
    await userEvent.click(screen.getByText('t2'))
    expect(screen.getByTestId('t')).toHaveTextContent('t2|Inmobiliaria Norte')
  })

  it('ignora la selección de un tenant ajeno', async () => {
    setup('tenant_manager') // solo tiene t1 y t2
    await waitFor(() => expect(screen.getByTestId('t')).toHaveTextContent('t1'))
    await userEvent.click(screen.getByText('t3'))
    expect(screen.getByTestId('t')).toHaveTextContent('t1|Clínica Vital')
  })

  it('el cliente queda fijo en su único tenant', async () => {
    setup('client')
    await waitFor(() => expect(screen.getByTestId('t')).toHaveTextContent('t1|Clínica Vital|false|1'))
  })
})
