import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { LANGUAGE_STORAGE_KEY } from '@/core/i18n/i18n'
import { fakeAuthApi, makeUser, renderApp } from '@/test/renderApp'

async function openMenu() {
  const trigger = await screen.findByRole('button', { name: /Menú de usuario|User menu|Menú d'usuari/ })
  await userEvent.click(trigger)
  return within(trigger.parentElement!)
}

describe('UserMenu: idioma', () => {
  it('muestra el idioma activo y cambia toda la consola al elegir otro', async () => {
    renderApp('/dashboard', fakeAuthApi(makeUser('admin')))
    const menu = await openMenu()
    await userEvent.click(menu.getByRole('button', { name: /Idioma/ }))
    expect(menu.getByRole('radio', { name: 'Español' })).toHaveAttribute('aria-checked', 'true')

    await userEvent.click(menu.getByRole('radio', { name: 'English' }))

    expect(await screen.findByRole('heading', { level: 1, name: 'Dashboard' })).toBeInTheDocument()
    const [sidebar] = screen.getAllByRole('navigation', { name: 'Main' })
    expect(within(sidebar!).getByRole('link', { name: 'Settings' })).toBeInTheDocument()
    expect(screen.getByText('Weekly activity')).toBeInTheDocument()
    expect(localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe('en')
    expect(document.documentElement.lang).toBe('en')
  })

  it('en catalán traduce el menú y los textos del perfil', async () => {
    renderApp('/dashboard', fakeAuthApi(makeUser('client')))
    const menu = await openMenu()
    await userEvent.click(menu.getByRole('button', { name: /Idioma/ }))
    await userEvent.click(menu.getByRole('radio', { name: 'Català' }))

    const again = await openMenu()
    expect(again.getByRole('link', { name: 'El meu perfil' })).toBeInTheDocument()
    expect(again.getByRole('link', { name: 'Suport' })).toBeInTheDocument()
    expect(again.getByRole('button', { name: 'Tancar la sessió' })).toBeInTheDocument()
  })
})
