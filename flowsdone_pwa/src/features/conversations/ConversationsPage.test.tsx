import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { createMockAdminApi } from '@/core/admin/mockAdminApi'
import { SEED } from '@/test/adminFixtures'
import { fakeAuthApi, makeUser, renderApp } from '@/test/renderApp'

const setup = (role: 'admin' | 'botmaster' = 'admin') => {
  const admin = createMockAdminApi({ latencyMs: 0, seed: SEED })
  renderApp('/conversations', fakeAuthApi(makeUser(role)), admin)
  return admin
}

describe('ConversationsPage', { timeout: 20_000 }, () => {
  it('lista las conversaciones y al abrir una muestra la transcripción y su consumo', async () => {
    setup()
    const list = await screen.findByRole('list', { name: 'Conversaciones' }, { timeout: 5000 })
    const items = within(list).getAllByRole('button')
    expect(items.length).toBeGreaterThan(0)

    await userEvent.click(items[0]!)

    const transcript = await screen.findByRole('list', { name: 'Transcripción' }, { timeout: 5000 })
    expect(within(transcript).getAllByRole('listitem').length).toBeGreaterThan(1)
    expect(screen.getByText('Consumo de la conversación')).toBeInTheDocument()
    expect(screen.getByText('Coste para Flowsdone')).toBeInTheDocument()
  })

  it('filtra por canal y por contacto', async () => {
    const admin = setup()
    const list = vi.spyOn(admin, 'listConversations')
    await screen.findByRole('list', { name: 'Conversaciones' }, { timeout: 5000 })

    await userEvent.selectOptions(screen.getByLabelText('Canal'), 'telegram')
    const items = within(await screen.findByRole('list', { name: 'Conversaciones' }, { timeout: 5000 })).getAllByRole('button')
    expect(items.every((b) => b.textContent?.includes('Telegram'))).toBe(true)
    expect(list).toHaveBeenLastCalledWith(expect.objectContaining({ channel_type: 'telegram' }))

    await userEvent.type(screen.getByLabelText('Contacto'), 'usuario11')
    expect(await screen.findByText('@usuario11')).toBeInTheDocument()
    expect(list).toHaveBeenLastCalledWith(expect.objectContaining({ contact: 'usuario11', channel_type: 'telegram' }))
  })

  it('sin resultados muestra el estado vacío', async () => {
    setup()
    await screen.findByRole('list', { name: 'Conversaciones' }, { timeout: 5000 })
    await userEvent.type(screen.getByLabelText('Contacto'), 'nadie-con-este-nombre')
    expect(await screen.findByText('No hay conversaciones')).toBeInTheDocument()
  })
})
