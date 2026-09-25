import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { AuthError } from '@/core/auth/AuthApi'
import { DEMO_ACCOUNTS } from '@/core/auth/mockAuthApi'
import { fakeAuthApi, makeUser, renderApp } from '@/test/renderApp'

const h1 = (name: string | RegExp) => screen.findByRole('heading', { level: 1, name })

describe('LoginPage', () => {
  it('el botón está deshabilitado hasta completar ambos campos', async () => {
    renderApp('/login', fakeAuthApi(null))
    await h1('Inicia sesión')
    const submit = screen.getByRole('button', { name: 'Ingresar' })
    expect(submit).toBeDisabled()
    await userEvent.type(screen.getByLabelText('Correo electrónico'), 'a@b.c')
    expect(submit).toBeDisabled()
    await userEvent.type(screen.getByLabelText('Contraseña'), 'secreto')
    expect(submit).toBeEnabled()
  })

  it('alterna la visibilidad de la contraseña', async () => {
    renderApp('/login', fakeAuthApi(null))
    await h1('Inicia sesión')
    const input = screen.getByLabelText('Contraseña')
    expect(input).toHaveAttribute('type', 'password')
    await userEvent.click(screen.getByRole('button', { name: 'Mostrar contraseña' }))
    expect(input).toHaveAttribute('type', 'text')
    expect(screen.getByRole('button', { name: 'Ocultar contraseña' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('muestra el error de credenciales en un alert y deja reintentar', async () => {
    const api = {
      ...fakeAuthApi(null),
      login: vi.fn().mockRejectedValue(new AuthError('invalid_credentials', 'Correo o contraseña incorrectos.')),
    }
    renderApp('/login', api)
    await h1('Inicia sesión')
    await userEvent.type(screen.getByLabelText('Correo electrónico'), 'a@b.c')
    await userEvent.type(screen.getByLabelText('Contraseña'), 'mala')
    await userEvent.click(screen.getByRole('button', { name: 'Ingresar' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Correo o contraseña incorrectos.')
    expect(screen.getByRole('button', { name: 'Ingresar' })).toBeEnabled()
  })

  it('un error no controlado muestra un mensaje genérico', async () => {
    const api = { ...fakeAuthApi(null), login: vi.fn().mockRejectedValue(new Error('boom')) }
    renderApp('/login', api)
    await h1('Inicia sesión')
    await userEvent.type(screen.getByLabelText('Correo electrónico'), 'a@b.c')
    await userEvent.type(screen.getByLabelText('Contraseña'), 'x')
    await userEvent.click(screen.getByRole('button', { name: 'Ingresar' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Ocurrió un error inesperado.')
  })

  it('un login correcto lleva a la página de inicio del perfil', async () => {
    const user = makeUser('botmaster')
    let session: typeof user | null = null
    const api = { ...fakeAuthApi(null), restore: async () => session, login: async () => (session = user) }
    renderApp('/login', api)
    await h1('Inicia sesión')
    await userEvent.type(screen.getByLabelText('Correo electrónico'), user.email)
    await userEvent.type(screen.getByLabelText('Contraseña'), 'x')
    await userEvent.click(screen.getByRole('button', { name: 'Ingresar' }))
    expect(await h1('Dashboard')).toBeInTheDocument()
  })

  it('tras el login vuelve a la ruta que se intentó abrir', async () => {
    const user = makeUser('admin')
    let session: typeof user | null = null
    const api = { ...fakeAuthApi(null), restore: async () => session, login: async () => (session = user) }
    renderApp('/channels', api) // sin sesión -> /login con from=/channels
    await h1('Inicia sesión')
    await userEvent.type(screen.getByLabelText('Correo electrónico'), user.email)
    await userEvent.type(screen.getByLabelText('Contraseña'), 'x')
    await userEvent.click(screen.getByRole('button', { name: 'Ingresar' }))
    expect(await h1('Canales')).toBeInTheDocument()
  })

  it('en modo mock ofrece cuentas demo que rellenan el formulario', async () => {
    renderApp('/login', fakeAuthApi(null))
    await h1('Inicia sesión')
    const demo = DEMO_ACCOUNTS.find((a) => a.role === 'client')!
    await userEvent.click(screen.getByRole('button', { name: /Cliente/ }))
    await waitFor(() => expect(screen.getByLabelText('Correo electrónico')).toHaveValue(demo.email))
    expect(screen.getByLabelText('Contraseña')).toHaveValue(demo.password)
  })
})
