import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { AuthError } from '@/core/auth/AuthApi'
import { fakeAuthApi, makeUser, renderApp } from '@/test/renderApp'

const h1 = (name: string | RegExp) => screen.findByRole('heading', { level: 1, name })

describe('ActivateAccountPage', () => {
  it('el botón sigue deshabilitado hasta que ambas contraseñas coinciden y cumplen el mínimo', async () => {
    renderApp('/activate-account/tok-1', fakeAuthApi(null))
    await h1('Activa tu cuenta')
    const submit = screen.getByRole('button', { name: 'Activar mi cuenta' })
    expect(submit).toBeDisabled()

    await userEvent.type(screen.getByLabelText('Contraseña'), 'corta')
    expect(submit).toBeDisabled()

    await userEvent.clear(screen.getByLabelText('Contraseña'))
    await userEvent.type(screen.getByLabelText('Contraseña'), 'x'.repeat(10))
    await userEvent.type(screen.getByLabelText('Confirma la contraseña'), 'y'.repeat(10))
    expect(submit).toBeEnabled() // habilitado; el mismatch se avisa al enviar

    await userEvent.click(submit)
    expect(await screen.findByRole('alert')).toHaveTextContent('Las contraseñas no coinciden.')
  })

  it('activa la cuenta y entra directo (auto-login)', async () => {
    const user = makeUser('botmaster')
    const api = { ...fakeAuthApi(null), activateAccount: vi.fn().mockResolvedValue(user) }
    renderApp('/activate-account/tok-1', api)
    await h1('Activa tu cuenta')

    await userEvent.type(screen.getByLabelText('Contraseña'), 'x'.repeat(10))
    await userEvent.type(screen.getByLabelText('Confirma la contraseña'), 'x'.repeat(10))
    await userEvent.click(screen.getByRole('button', { name: 'Activar mi cuenta' }))

    expect(await h1('Dashboard')).toBeInTheDocument()
    expect(api.activateAccount).toHaveBeenCalledWith('tok-1', 'x'.repeat(10))
  })

  it('funciona aunque este navegador ya tenga la sesión de OTRA cuenta abierta', async () => {
    // Regresión: un admin abriendo el link de activación de otro usuario en el
    // mismo navegador no debe rebotar a su propio dashboard (no lleva PublicOnly
    // a propósito - ver router.tsx) - el form tiene que mostrarse y funcionar.
    const admin = makeUser('admin')
    const newUser = makeUser('botmaster')
    const api = { ...fakeAuthApi(admin), activateAccount: vi.fn().mockResolvedValue(newUser) }
    renderApp('/activate-account/tok-1', api)

    // No debe rebotar a /dashboard del admin.
    await h1('Activa tu cuenta')

    await userEvent.type(screen.getByLabelText('Contraseña'), 'x'.repeat(10))
    await userEvent.type(screen.getByLabelText('Confirma la contraseña'), 'x'.repeat(10))
    await userEvent.click(screen.getByRole('button', { name: 'Activar mi cuenta' }))

    // Termina en el inicio del usuario recién activado (botmaster), no en el del admin.
    expect(await h1('Dashboard')).toBeInTheDocument()
    expect(api.activateAccount).toHaveBeenCalledWith('tok-1', 'x'.repeat(10))
  })

  it('un enlace inválido o vencido muestra el error del servidor', async () => {
    const api = {
      ...fakeAuthApi(null),
      activateAccount: vi.fn().mockRejectedValue(new AuthError('invalid_token', 'El enlace no es válido o ya venció. Pide uno nuevo.')),
    }
    renderApp('/activate-account/tok-vencido', api)
    await h1('Activa tu cuenta')

    await userEvent.type(screen.getByLabelText('Contraseña'), 'x'.repeat(10))
    await userEvent.type(screen.getByLabelText('Confirma la contraseña'), 'x'.repeat(10))
    await userEvent.click(screen.getByRole('button', { name: 'Activar mi cuenta' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('El enlace no es válido o ya venció. Pide uno nuevo.')
  })
})
