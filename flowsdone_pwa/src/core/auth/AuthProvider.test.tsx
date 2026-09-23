import { act, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { AuthProvider } from './AuthProvider'
import { useAuth } from './useAuth'
import { fakeAuthApi, makeUser } from '@/test/renderApp'

function Probe() {
  const { status, user, login, logout, refreshUser } = useAuth()
  return (
    <div>
      <span data-testid="s">{`${status}|${user?.role ?? '-'}`}</span>
      <span data-testid="tenants">{user?.tenants.map((t) => t.name).join(',') ?? '-'}</span>
      <button onClick={() => void refreshUser()}>refrescar</button>
      <button onClick={() => void login({ email: 'a', password: 'b' })}>login</button>
      <button onClick={() => void logout()}>logout</button>
    </div>
  )
}

describe('AuthProvider', () => {
  it('empieza en loading y pasa a authenticated si hay sesión', async () => {
    render(<AuthProvider api={fakeAuthApi(makeUser('admin'))}><Probe /></AuthProvider>)
    expect(screen.getByTestId('s')).toHaveTextContent('loading|-')
    await waitFor(() => expect(screen.getByTestId('s')).toHaveTextContent('authenticated|admin'))
  })

  it('pasa a anonymous si no hay sesión', async () => {
    render(<AuthProvider api={fakeAuthApi(null)}><Probe /></AuthProvider>)
    await waitFor(() => expect(screen.getByTestId('s')).toHaveTextContent('anonymous|-'))
  })

  it('un restore que falla se trata como sin sesión', async () => {
    const api = { ...fakeAuthApi(null), restore: () => Promise.reject(new Error('boom')) }
    render(<AuthProvider api={api}><Probe /></AuthProvider>)
    await waitFor(() => expect(screen.getByTestId('s')).toHaveTextContent('anonymous|-'))
  })

  it('login y logout actualizan el estado', async () => {
    const user = makeUser('client')
    const api = { ...fakeAuthApi(null), login: vi.fn().mockResolvedValue(user) }
    render(<AuthProvider api={api}><Probe /></AuthProvider>)
    await waitFor(() => expect(screen.getByTestId('s')).toHaveTextContent('anonymous'))

    await act(async () => screen.getByText('login').click())
    expect(screen.getByTestId('s')).toHaveTextContent('authenticated|client')

    await act(async () => screen.getByText('logout').click())
    expect(screen.getByTestId('s')).toHaveTextContent('anonymous|-')
  })

  it('logout cierra la sesión local aunque el adaptador falle', async () => {
    const api = { ...fakeAuthApi(makeUser('admin')), logout: () => Promise.reject(new Error('x')) }
    render(<AuthProvider api={api}><Probe /></AuthProvider>)
    await waitFor(() => expect(screen.getByTestId('s')).toHaveTextContent('authenticated'))
    await act(async () => {
      screen.getByText('logout').click()
    })
    await waitFor(() => expect(screen.getByTestId('s')).toHaveTextContent('anonymous'))
  })

  it('useAuth falla con mensaje claro fuera del provider', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    expect(() => render(<Probe />)).toThrow(/AuthProvider/)
    spy.mockRestore()
  })

  it('refreshUser vuelve a pedir al usuario (p. ej. sus tenants cambiaron) sin cerrar la sesión', async () => {
    const before = makeUser('admin')
    const after = { ...before, tenants: [...before.tenants, { id: 't-new', name: 'Tenant Nuevo' }] }
    let current = before
    const api = { ...fakeAuthApi(null), restore: async () => current, login: async () => current }
    render(<AuthProvider api={api}><Probe /></AuthProvider>)
    await waitFor(() => expect(screen.getByTestId('s')).toHaveTextContent('authenticated'))
    expect(screen.getByTestId('tenants').textContent).not.toContain('Tenant Nuevo')

    current = after
    await act(async () => screen.getByText('refrescar').click())
    expect(screen.getByTestId('tenants').textContent).toContain('Tenant Nuevo')
    expect(screen.getByTestId('s')).toHaveTextContent('authenticated')
  })

  it('refreshUser ignora un resultado vacío (fallo de red) en vez de cerrar la sesión', async () => {
    let calls = 0
    const api = { ...fakeAuthApi(null), restore: async () => (calls++ === 0 ? makeUser('client') : null), login: async () => makeUser('client') }
    render(<AuthProvider api={api}><Probe /></AuthProvider>)
    await waitFor(() => expect(screen.getByTestId('s')).toHaveTextContent('authenticated|client'))

    await act(async () => screen.getByText('refrescar').click())
    expect(screen.getByTestId('s')).toHaveTextContent('authenticated|client')
  })
})
