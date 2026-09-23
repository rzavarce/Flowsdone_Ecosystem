import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { AuthError } from '@/core/auth/AuthApi'
import { fakeAuthApi, renderApp } from '@/test/renderApp'

const h1 = (name: string | RegExp) => screen.findByRole('heading', { level: 1, name })

describe('ForgotPasswordPage', () => {
  it('tras enviar, muestra el mismo mensaje exista o no la cuenta', async () => {
    const api = { ...fakeAuthApi(null), requestPasswordReset: vi.fn().mockResolvedValue(undefined) }
    renderApp('/recuperar-password', api)
    await h1('Recupera tu contraseña')

    await userEvent.type(screen.getByLabelText('Correo electrónico'), 'ghost@x.com')
    await userEvent.click(screen.getByRole('button', { name: 'Enviar enlace de recuperación' }))

    expect(await screen.findByText(/te llegará un enlace/)).toBeInTheDocument()
    expect(api.requestPasswordReset).toHaveBeenCalledWith('ghost@x.com')
    expect(screen.queryByLabelText('Correo electrónico')).not.toBeInTheDocument() // se reemplaza el form
  })

  it('el aviso de éxito se puede quitar y vuelve a mostrar el formulario', async () => {
    const api = { ...fakeAuthApi(null), requestPasswordReset: vi.fn().mockResolvedValue(undefined) }
    renderApp('/recuperar-password', api)
    await h1('Recupera tu contraseña')

    await userEvent.type(screen.getByLabelText('Correo electrónico'), 'ghost@x.com')
    await userEvent.click(screen.getByRole('button', { name: 'Enviar enlace de recuperación' }))
    await screen.findByText(/te llegará un enlace/)

    await userEvent.click(screen.getByRole('button', { name: 'Quitar aviso' }))
    expect(screen.queryByText(/te llegará un enlace/)).not.toBeInTheDocument()
    // El email queda tal como se escribió, por si hay que corregir un typo.
    expect(screen.getByLabelText('Correo electrónico')).toHaveValue('ghost@x.com')
  })

  it('un límite de intentos sí se muestra (no revela existencia, solo frena abuso)', async () => {
    const api = {
      ...fakeAuthApi(null),
      requestPasswordReset: vi.fn().mockRejectedValue(new AuthError('rate_limited', 'Demasiados intentos. Espera unos minutos e inténtalo de nuevo.')),
    }
    renderApp('/recuperar-password', api)
    await h1('Recupera tu contraseña')

    await userEvent.type(screen.getByLabelText('Correo electrónico'), 'a@b.c')
    await userEvent.click(screen.getByRole('button', { name: 'Enviar enlace de recuperación' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Demasiados intentos')
    expect(screen.getByLabelText('Correo electrónico')).toBeInTheDocument() // el form sigue ahí
  })

  it('tiene un link de vuelta a login', async () => {
    renderApp('/recuperar-password', fakeAuthApi(null))
    await h1('Recupera tu contraseña')
    expect(screen.getByRole('link', { name: 'Volver a iniciar sesión' })).toHaveAttribute('href', '/login')
  })
})
