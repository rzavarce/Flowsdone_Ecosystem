import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { createMockAdminApi } from '@/core/admin/mockAdminApi'
import { SEED } from '@/test/adminFixtures'
import { fakeAuthApi, makeUser, renderApp } from '@/test/renderApp'

const names = () =>
  within(screen.getByRole('list', { name: 'Usuarios' }))
    .getAllByRole('listitem')
    .map((li) => li.querySelector('.font-medium')?.textContent)

const setup = async (path = '/users') => {
  renderApp(path, fakeAuthApi(makeUser('admin')), createMockAdminApi({ latencyMs: 0, seed: SEED }))
  await screen.findByRole('list', { name: path === '/users' ? 'Usuarios' : 'Tenants' }, { timeout: 5000 })
}

describe('Usuarios: buscador, filtros y tenant activo', { timeout: 20_000 }, () => {
  it('con "Todos los tenants" lista todo el staff (sin clientes)', async () => {
    await setup()
    expect(names()).toEqual(['Ana Admin', 'Marcos Gestor', 'Bea Botmaster'])
  })

  it('al elegir un tenant arriba solo quedan sus usuarios', async () => {
    await setup()
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Tenant activo' }), 't2')
    expect(names()).toEqual(['Bea Botmaster'])
    expect(screen.getByText(/Usuarios de Inmobiliaria Norte/)).toBeInTheDocument()
  })

  it('busca por nombre o email sin importar mayúsculas ni acentos, y filtra por rol y estado', async () => {
    await setup()
    await userEvent.type(screen.getByLabelText('Buscar usuario'), 'MARCOS@')
    expect(names()).toEqual(['Marcos Gestor'])

    await userEvent.clear(screen.getByLabelText('Buscar usuario'))
    await userEvent.selectOptions(screen.getByLabelText('Rol'), 'botmaster')
    expect(names()).toEqual(['Bea Botmaster'])

    await userEvent.selectOptions(screen.getByLabelText('Estado'), 'active')
    expect(await screen.findByText('Ningún usuario coincide')).toBeInTheDocument()
  })
})

describe('Tenants: buscador', { timeout: 20_000 }, () => {
  it('filtra la lista por nombre o identificador', async () => {
    await setup('/tenants')
    await userEvent.type(screen.getByLabelText('Buscar tenant'), 'norte')
    const items = within(screen.getByRole('list', { name: 'Tenants' })).getAllByRole('button')
    expect(items.map((b) => b.textContent)).toEqual([expect.stringContaining('Inmobiliaria Norte')])

    await userEvent.clear(screen.getByLabelText('Buscar tenant'))
    await userEvent.type(screen.getByLabelText('Buscar tenant'), 'zzz')
    expect(screen.getByText('Ningún tenant coincide con la búsqueda.')).toBeInTheDocument()
  })
})
