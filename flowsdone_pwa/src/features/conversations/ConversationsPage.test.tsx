import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { AdminApi } from '@/core/admin/AdminApi'
import { createMockAdminApi } from '@/core/admin/mockAdminApi'
import { ApiError } from '@/core/http/apiFetch'
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

  it('las conversaciones de los enlaces compartidos se ven y se filtran como "Demo"', async () => {
    const admin = setup()
    const list = vi.spyOn(admin, 'listConversations')
    await screen.findByRole('list', { name: 'Conversaciones' }, { timeout: 5000 })

    await userEvent.selectOptions(screen.getByLabelText('Canal'), 'demo')

    expect(list).toHaveBeenLastCalledWith(expect.objectContaining({ channel_type: 'demo' }))
    const [item] = within(await screen.findByRole('list', { name: 'Conversaciones' }, { timeout: 5000 })).getAllByRole('button')
    expect(item).toHaveTextContent('Demo · visitante 1a2b3c4d')
    expect(item).toHaveTextContent('Demo (enlaces compartidos)')
  })

  it('se pone nombre al contacto desde la conversación y se ve en la lista y en la búsqueda', async () => {
    const admin = setup()
    const update = vi.spyOn(admin, 'updateConversationContact')
    const list = await screen.findByRole('list', { name: 'Conversaciones' }, { timeout: 5000 })
    const [first] = within(list).getAllByRole('button')
    const identifier = first!.querySelector('.font-medium')!.textContent!
    await userEvent.click(first!)

    await userEvent.click(await screen.findByRole('button', { name: 'Añadir datos' }, { timeout: 5000 }))
    const dialog = screen.getByRole('dialog', { name: 'Editar contacto' })
    await userEvent.type(within(dialog).getByLabelText('Nombre'), 'Ana Pérez')
    await userEvent.type(within(dialog).getByLabelText('Email'), 'Ana@Example.com')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Guardar' }))

    expect(update).toHaveBeenCalledWith(expect.any(String), { name: 'Ana Pérez', email: 'Ana@Example.com' })
    expect(await screen.findByRole('heading', { name: 'Ana Pérez' }, { timeout: 5000 })).toBeInTheDocument()
    expect(screen.getByText('ana@example.com')).toBeInTheDocument()
    const named = within(screen.getByRole('list', { name: 'Conversaciones' })).getAllByRole('button')[0]!
    expect(named).toHaveTextContent('Ana Pérez')
    expect(named).toHaveTextContent(identifier)

    await userEvent.type(screen.getByLabelText('Contacto'), 'pérez')
    await vi.waitFor(() => expect(within(screen.getByRole('list', { name: 'Conversaciones' })).getAllByRole('button')).toHaveLength(1))
  })

  it('un email no válido se rechaza sin cerrar el diálogo', async () => {
    setup()
    const list = await screen.findByRole('list', { name: 'Conversaciones' }, { timeout: 5000 })
    await userEvent.click(within(list).getAllByRole('button')[0]!)
    await userEvent.click(await screen.findByRole('button', { name: 'Añadir datos' }, { timeout: 5000 }))
    const dialog = screen.getByRole('dialog', { name: 'Editar contacto' })

    await userEvent.type(within(dialog).getByLabelText('Email'), 'ana(at)example')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Guardar' }))

    expect(await within(dialog).findByRole('alert')).toBeInTheDocument()
    expect(screen.getByRole('dialog', { name: 'Editar contacto' })).toBeInTheDocument()
  })

  it('muestra solo las 10 últimas y "Cargar más" trae las siguientes', async () => {
    const admin = setup()
    const list = vi.spyOn(admin, 'listConversations')
    const items = () => within(screen.getByRole('list', { name: 'Conversaciones' })).getAllByRole('button')
    await screen.findByRole('list', { name: 'Conversaciones' }, { timeout: 5000 })

    expect(items()).toHaveLength(10)
    expect(list).toHaveBeenLastCalledWith(expect.objectContaining({ limit: 10 }))

    await userEvent.click(screen.getByRole('button', { name: 'Cargar más' }))
    // The next page: the 10 before the last one shown.
    await vi.waitFor(() =>
      expect(list).toHaveBeenLastCalledWith(expect.objectContaining({ limit: 10, before: expect.any(String) })),
    )
  })

  it('sin resultados muestra el estado vacío', async () => {
    setup()
    await screen.findByRole('list', { name: 'Conversaciones' }, { timeout: 5000 })
    await userEvent.type(screen.getByLabelText('Contacto'), 'nadie-con-este-nombre')
    expect(await screen.findByText('No hay conversaciones')).toBeInTheDocument()
  })
})

describe('pasar a CRM', () => {
  const openConversation = async (overrides: Partial<AdminApi>) => {
    const admin = { ...createMockAdminApi({ latencyMs: 0, seed: SEED }), ...overrides }
    const detail = await admin.getConversation((await admin.listConversations({}))[0]!.id)
    admin.getConversation = vi.fn().mockResolvedValue({ ...detail, conversation: { ...detail.conversation, status: 'open' } })
    renderApp('/conversations', fakeAuthApi(makeUser('admin')), admin)
    const list = await screen.findByRole('list', { name: 'Conversaciones' }, { timeout: 5000 })
    await userEvent.click(within(list).getAllByRole('button')[0]!)
    await userEvent.click(await screen.findByRole('button', { name: 'Pasar a CRM' }, { timeout: 5000 }))
    return { admin, detail, dialog: screen.getByRole('dialog', { name: 'Pasar la conversación al CRM' }) }
  }

  it('traspasa la conversación abierta con el motivo', async () => {
    const start = vi.fn().mockResolvedValue({ id: 'h1', conversation_id: 'x', integration_id: 'i1', status: 'open', opened_at: '' })
    const { detail, dialog } = await openConversation({ startCrmHandoff: start })

    await userEvent.type(within(dialog).getByLabelText('Motivo'), 'Quiere hablar con una persona')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Pasar a CRM' }))

    await waitFor(() => expect(start).toHaveBeenCalledWith(detail.conversation.id, 'Quiere hablar con una persona'))
    expect(await screen.findByText(/Conversación traspasada/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'En el CRM' })).toBeDisabled()
  })

  it('sin integración de CRM lo explica y deja el diálogo abierto', async () => {
    const start = vi.fn().mockRejectedValue(new ApiError(409, 'the project has no active CRM integration'))
    const { dialog } = await openConversation({ startCrmHandoff: start })

    await userEvent.click(within(dialog).getByRole('button', { name: 'Pasar a CRM' }))

    expect(await within(dialog).findByText(/no tiene una integración de CRM activa/)).toBeInTheDocument()
  })
})
