import { useQuery } from '@tanstack/react-query'
import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '@/core/auth/AuthProvider'
import { useAuth } from '@/core/auth/useAuth'
import { ApiError } from '@/core/http/apiFetch'
import { makeUser } from '@/test/renderApp'
import type { AuthApi } from '@/core/auth/AuthApi'
import type { AdminApi } from './AdminApi'
import { AdminApiProvider } from './AdminApiProvider'
import { shouldRetry } from './retry'
import { useAdminApi } from './useAdminApi'

function Probe() {
  const api = useAdminApi()
  const { status, user, login, logout } = useAuth()
  const q = useQuery({ queryKey: ['probe'], queryFn: () => api.listProjects() })
  return (
    <div>
      <span data-testid="auth">{`${status}|${user?.id ?? '-'}`}</span>
      <span data-testid="data">{q.data ? q.data.length : q.error ? 'error' : 'loading'}</span>
      <button onClick={() => void logout()}>salir</button>
      <button onClick={() => void login({ email: 'b@x.co', password: 'x' })}>entrar como B</button>
    </div>
  )
}

/** Como `RequireAuth` en la app real: las pantallas con datos solo existen con sesión. */
function Gate({ children }: { children: ReactNode }) {
  const { status } = useAuth()
  return status === 'authenticated' ? <>{children}</> : <span data-testid="gate">{status}</span>
}

const stubAdmin = (listProjects: () => Promise<never[]>) => ({ listProjects }) as unknown as AdminApi

describe('shouldRetry', () => {
  it('no reintenta errores del cliente (4xx) pero sí los de red y 5xx, hasta 2 veces', () => {
    for (const status of [400, 401, 403, 404, 409, 422]) expect(shouldRetry(0, new ApiError(status, 'x'))).toBe(false)
    expect(shouldRetry(0, new ApiError(500, 'x'))).toBe(true)
    expect(shouldRetry(1, new ApiError(0, 'sin red'))).toBe(true)
    expect(shouldRetry(2, new ApiError(500, 'x'))).toBe(false)
  })
})

describe('AdminApiProvider', () => {
  it('un 401 cierra la sesión; un 403 o 404 no', async () => {
    for (const [status, expected] of [[401, 'anonymous'], [403, 'authenticated'], [404, 'authenticated']] as const) {
      const authApi: AuthApi = { restore: async () => makeUser('admin'), login: async () => makeUser('admin'), logout: async () => {} }
      const { unmount } = render(
        <AuthProvider api={authApi}>
          <AdminApiProvider api={stubAdmin(() => Promise.reject(new ApiError(status, 'x')))}>
            <Gate>
              <Probe />
            </Gate>
          </AdminApiProvider>
        </AuthProvider>,
      )
      // Con un 401 la sesión se cierra y el Gate desmonta el Probe; con 403/404 sigue visible.
      if (expected === 'anonymous') {
        await waitFor(() => expect(screen.getByTestId('gate')).toHaveTextContent('anonymous'))
      } else {
        await waitFor(() => expect(screen.getByTestId('data')).toHaveTextContent('error'))
        expect(screen.getByTestId('auth').textContent!.startsWith(expected)).toBe(true)
      }
      unmount()
    }
  })

  it('un 4xx se pide una sola vez (sin reintentos)', async () => {
    const list = vi.fn().mockRejectedValue(new ApiError(403, 'no'))
    render(
      <AuthProvider api={{ restore: async () => makeUser('admin'), login: async () => makeUser('admin'), logout: async () => {} }}>
        <AdminApiProvider api={stubAdmin(list)}>
          <Gate>
            <Probe />
          </Gate>
        </AdminApiProvider>
      </AuthProvider>,
    )
    await waitFor(() => expect(screen.getByTestId('data')).toHaveTextContent('error'))
    expect(list).toHaveBeenCalledTimes(1)
  })

  it('la caché no se filtra entre personas: al cambiar de usuario se vuelve a pedir', async () => {
    const userA = makeUser('admin')
    const userB = { ...makeUser('client'), id: 'u-b' }
    let session: typeof userA | null = userA
    const authApi: AuthApi = {
      restore: async () => session,
      login: async () => (session = userB),
      logout: async () => void (session = null),
    }
    const list = vi.fn().mockResolvedValue([])
    render(
      <AuthProvider api={authApi}>
        <AdminApiProvider api={stubAdmin(list)}>
          <Probe />
        </AdminApiProvider>
      </AuthProvider>,
    )
    await waitFor(() => expect(screen.getByTestId('data')).toHaveTextContent('0'))
    const callsForA = list.mock.calls.length

    await userEvent.click(screen.getByText('salir'))
    await userEvent.click(screen.getByText('entrar como B'))
    await waitFor(() => expect(screen.getByTestId('auth')).toHaveTextContent('authenticated|u-b'))
    await waitFor(() => expect(list.mock.calls.length).toBeGreaterThan(callsForA))
  })

  it('useAdminApi falla con un mensaje claro fuera del provider', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    function Bare() {
      useAdminApi()
      return null
    }
    expect(() => act(() => void render(<Bare />))).toThrow(/AdminApiProvider/)
    spy.mockRestore()
  })
})
