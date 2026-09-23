import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { AuthError } from '@/core/auth/AuthApi'
import { fakeAuthApi, makeUser, renderApp } from '@/test/renderApp'

const h1 = (name: string | RegExp) => screen.findByRole('heading', { level: 1, name })

describe('ResetPasswordPage', () => {
  it('fija la contraseña nueva y entra directo (auto-login)', async () => {
    const user = makeUser('client')
    const api = { ...fakeAuthApi(null), resetPassword: vi.fn().mockResolvedValue(user) }
    renderApp('/reset-password/tok-1', api)
    await h1('Crea una nueva contraseña')

    await userEvent.type(screen.getByLabelText('Contraseña nueva'), 'x'.repeat(10))
    await userEvent.type(screen.getByLabelText('Confirma la contraseña'), 'x'.repeat(10))
    await userEvent.click(screen.getByRole('button', { name: 'Guardar contraseña' }))

    expect(await h1('Mi panel')).toBeInTheDocument()
    expect(api.resetPassword).toHaveBeenCalledWith('tok-1', 'x'.repeat(10))
  })

  it('funciona aunque este navegador ya tenga la sesión de OTRA cuenta abierta', async () => {
    // Regresión: no lleva PublicOnly a propósito (ver router.tsx) - un link de
    // reset debe funcionar sin importar qué sesión haya en este navegador.
    const admin = makeUser('admin')
    const targetUser = makeUser('client')
    const api = { ...fakeAuthApi(admin), resetPassword: vi.fn().mockResolvedValue(targetUser) }
    renderApp('/reset-password/tok-1', api)

    await h1('Crea una nueva contraseña') // no rebota a /dashboard del admin

    await userEvent.type(screen.getByLabelText('Contraseña nueva'), 'x'.repeat(10))
    await userEvent.type(screen.getByLabelText('Confirma la contraseña'), 'x'.repeat(10))
    await userEvent.click(screen.getByRole('button', { name: 'Guardar contraseña' }))

    expect(await h1('Mi panel')).toBeInTheDocument() // el inicio del usuario del token, no del admin
    expect(api.resetPassword).toHaveBeenCalledWith('tok-1', 'x'.repeat(10))
  })

  it('un enlace inválido ofrece pedir uno nuevo', async () => {
    const api = {
      ...fakeAuthApi(null),
      resetPassword: vi.fn().mockRejectedValue(new AuthError('invalid_token', 'El enlace no es válido o ya venció. Pide uno nuevo.')),
    }
    renderApp('/reset-password/tok-vencido', api)
    await h1('Crea una nueva contraseña')

    await userEvent.type(screen.getByLabelText('Contraseña nueva'), 'x'.repeat(10))
    await userEvent.type(screen.getByLabelText('Confirma la contraseña'), 'x'.repeat(10))
    await userEvent.click(screen.getByRole('button', { name: 'Guardar contraseña' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('El enlace no es válido o ya venció.')
    expect(within(screen.getByRole('alert')).getByRole('link', { name: 'Pide un enlace nuevo' })).toHaveAttribute(
      'href',
      '/forgot-password',
    )
  })

  it('avisa si las contraseñas no coinciden, sin llamar al backend', async () => {
    const api = { ...fakeAuthApi(null), resetPassword: vi.fn() }
    renderApp('/reset-password/tok-1', api)
    await h1('Crea una nueva contraseña')

    await userEvent.type(screen.getByLabelText('Contraseña nueva'), 'x'.repeat(10))
    await userEvent.type(screen.getByLabelText('Confirma la contraseña'), 'y'.repeat(10))
    await userEvent.click(screen.getByRole('button', { name: 'Guardar contraseña' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Las contraseñas no coinciden.')
    expect(api.resetPassword).not.toHaveBeenCalled()
  })
})
