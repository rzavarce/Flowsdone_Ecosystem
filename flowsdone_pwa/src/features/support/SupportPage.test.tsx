import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { fakeAuthApi, makeUser, renderApp } from '@/test/renderApp'
import { FAQ_IDS } from './faq'

describe('SupportPage', () => {
  it('cualquier perfil llega desde el menú de usuario y ve las preguntas frecuentes', async () => {
    renderApp('/dashboard', fakeAuthApi(makeUser('consultant')))
    const trigger = await screen.findByRole('button', { name: 'Menú de usuario' })
    await userEvent.click(trigger)
    await userEvent.click(within(trigger.parentElement!).getByRole('link', { name: 'Soporte' }))

    expect(await screen.findByRole('heading', { level: 1, name: 'Soporte' })).toBeInTheDocument()
    expect(screen.getAllByRole('group')).toHaveLength(FAQ_IDS.length)
    expect(screen.getByText('¿Cómo cambio el idioma de la consola?')).toBeInTheDocument()
  })
})
