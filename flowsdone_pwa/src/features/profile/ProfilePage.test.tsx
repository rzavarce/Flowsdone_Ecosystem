import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { AuthError } from '@/core/auth/AuthApi'
import { ApiError } from '@/core/http/apiFetch'
import { fakeAuthApi, makeUser, renderApp } from '@/test/renderApp'

const h1 = (name: string) => screen.findByRole('heading', { level: 1, name })

/** Opens the user dropdown and returns a query scope limited to it (the sidebar has links too). */
async function openUserMenu() {
  const trigger = await screen.findByRole('button', { name: 'Menú de usuario' })
  await userEvent.click(trigger)
  return within(trigger.parentElement!)
}

describe('ProfilePage', () => {
  it('cualquier perfil puede ver su cuenta: nombre, email, rol y tenants', async () => {
    const user = makeUser('client')
    renderApp('/profile', fakeAuthApi(user))
    await h1('Mi perfil')
    expect(screen.getAllByText(user.email).length).toBeGreaterThan(0)
    expect(screen.getAllByText('Cliente').length).toBeGreaterThan(0)
    const tenants = screen.getByRole('list', { name: 'Tenants a los que tienes acceso' })
    expect(within(tenants).getByText('Clínica Vital')).toBeInTheDocument()
  })

  it('"Cambiar contraseña" envía el enlace al propio email y lo confirma', async () => {
    const user = makeUser('admin')
    const api = { ...fakeAuthApi(user), requestPasswordReset: vi.fn(async () => {}) }
    renderApp('/profile', api)
    await h1('Mi perfil')

    await userEvent.click(screen.getByRole('button', { name: 'Cambiar contraseña' }))
    expect(api.requestPasswordReset).toHaveBeenCalledWith(user.email)
    expect(await screen.findByText(/Revisa tu correo/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Enlace enviado' })).toBeDisabled()
  })

  it('si el envío falla muestra el error y deja reintentar', async () => {
    const api = {
      ...fakeAuthApi(makeUser('admin')),
      requestPasswordReset: vi.fn(async () => {
        throw new AuthError('rate_limited', 'Demasiados intentos.')
      }),
    }
    renderApp('/profile', api)
    await h1('Mi perfil')

    await userEvent.click(screen.getByRole('button', { name: 'Cambiar contraseña' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Demasiados intentos.')
    expect(screen.getByRole('button', { name: 'Cambiar contraseña' })).toBeEnabled()
  })
})

describe('UserMenu', () => {
  it('lleva a Mi perfil y se cierra al elegir', async () => {
    renderApp('/dashboard', fakeAuthApi(makeUser('admin')))
    await userEvent.click((await openUserMenu()).getByRole('link', { name: 'Mi perfil' }))
    expect(await h1('Mi perfil')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Mi perfil' })).not.toBeInTheDocument()
  })

  it('incluye Ajustes (todos los perfiles tienen settings:view) y Cerrar sesión', async () => {
    renderApp('/dashboard', fakeAuthApi(makeUser('client')))
    const menu = await openUserMenu()
    expect(menu.getByRole('link', { name: 'Ajustes' })).toHaveAttribute('href', '/settings')
    expect(menu.getByRole('button', { name: 'Cerrar sesión' })).toBeInTheDocument()
  })
})

// Mucho tecleo (userEvent.type) por test: con la suite completa en paralelo pasa de 5 s.
describe('edición del perfil', { timeout: 20_000 }, () => {
  /** Opens the edit dialog of a section by its accessible name. */
  async function openEdit(section: string) {
    await userEvent.click(await screen.findByRole('button', { name: `Editar: ${section}` }))
    return within(screen.getByRole('dialog'))
  }

  it('cambia nombre y teléfono y los muestra al guardar', async () => {
    renderApp('/profile', fakeAuthApi(makeUser('client')))
    await h1('Mi perfil')
    const dialog = await openEdit('Información personal')
    await userEvent.clear(dialog.getByLabelText('Nombre completo'))
    await userEvent.type(dialog.getByLabelText('Nombre completo'), 'Carla Nueva')
    await userEvent.type(dialog.getByLabelText(/Teléfono/), '+34 600 123 456')
    await userEvent.click(dialog.getByRole('button', { name: 'Guardar cambios' }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getAllByText('Carla Nueva').length).toBeGreaterThan(0)
    expect(screen.getByText('+34 600 123 456')).toBeInTheDocument()
  })

  it('no deja guardar un nombre vacío ni un teléfono con letras', async () => {
    const api = fakeAuthApi(makeUser('client'))
    const update = vi.spyOn(api, 'updateProfile')
    renderApp('/profile', api)
    await h1('Mi perfil')
    const dialog = await openEdit('Información personal')
    await userEvent.clear(dialog.getByLabelText('Nombre completo'))
    await userEvent.type(dialog.getByLabelText(/Teléfono/), 'llámame')
    await userEvent.click(dialog.getByRole('button', { name: 'Guardar cambios' }))

    expect(dialog.getByText('El nombre es obligatorio.')).toBeInTheDocument()
    expect(dialog.getByText(/Usa solo números/)).toBeInTheDocument()
    expect(update).not.toHaveBeenCalled()
  })

  it('guarda la dirección', async () => {
    renderApp('/profile', fakeAuthApi(makeUser('botmaster')))
    await h1('Mi perfil')
    const dialog = await openEdit('Dirección')
    await userEvent.type(dialog.getByLabelText(/Dirección/), 'Calle Mayor 1, Madrid')
    await userEvent.click(dialog.getByRole('button', { name: 'Guardar cambios' }))
    expect(await screen.findByText('Calle Mayor 1, Madrid')).toBeInTheDocument()
  })

  it('las redes exigen URLs http(s) y se muestran como enlaces', async () => {
    renderApp('/profile', fakeAuthApi(makeUser('client')))
    await h1('Mi perfil')
    const dialog = await openEdit('Redes sociales')
    await userEvent.type(dialog.getByLabelText('LinkedIn'), 'linkedin.com/in/carla')
    await userEvent.click(dialog.getByRole('button', { name: 'Guardar cambios' }))
    expect(dialog.getByText(/empiece por https/)).toBeInTheDocument()

    await userEvent.clear(dialog.getByLabelText('LinkedIn'))
    await userEvent.type(dialog.getByLabelText('LinkedIn'), 'https://www.linkedin.com/in/carla')
    await userEvent.click(dialog.getByRole('button', { name: 'Guardar cambios' }))

    const links = await screen.findAllByRole('link', { name: /linkedin/i })
    expect(links[0]).toHaveAttribute('href', 'https://www.linkedin.com/in/carla')
    expect(links[0]).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it('un error del servidor se muestra en el diálogo sin cerrarlo', async () => {
    const api = fakeAuthApi(makeUser('client'))
    api.updateProfile = vi.fn(async () => {
      throw new ApiError(400, 'phone must contain only digits')
    })
    renderApp('/profile', api)
    await h1('Mi perfil')
    const dialog = await openEdit('Dirección')
    await userEvent.type(dialog.getByLabelText(/Dirección/), 'X')
    await userEvent.click(dialog.getByRole('button', { name: 'Guardar cambios' }))
    expect(await dialog.findByText('phone must contain only digits')).toBeInTheDocument()
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('rechaza un archivo que no es imagen al cambiar la foto', async () => {
    const api = fakeAuthApi(makeUser('client'))
    const upload = vi.spyOn(api, 'uploadAvatar')
    renderApp('/profile', api)
    await h1('Mi perfil')
    const dialog = await openEdit('Foto de perfil')
    await userEvent.upload(dialog.getByLabelText('Subir foto'), new File(['%PDF'], 'cv.pdf', { type: 'application/pdf' }), {
      applyAccept: false,
    })
    expect(await dialog.findByText(/debe ser una imagen/)).toBeInTheDocument()
    expect(upload).not.toHaveBeenCalled()
  })
})
