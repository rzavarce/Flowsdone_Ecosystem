import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { fakeAuthApi, makeUser, renderApp } from '@/test/renderApp'

describe('Mi empresa: consumo', () => {
  it('el cliente ve su consumo del mes sin los costes de Flowsdone', async () => {
    renderApp('/company', fakeAuthApi(makeUser('client')))
    expect(await screen.findByText('3240 de 3000', undefined, { timeout: 5000 })).toBeInTheDocument()
    expect(screen.getByText('240 mensajes de excedente', { exact: false })).toBeInTheDocument()
    expect(screen.getByText('Total estimado del mes')).toBeInTheDocument()
    expect(screen.queryByText('Coste para Flowsdone')).not.toBeInTheDocument()
    expect(screen.queryByText('Margen')).not.toBeInTheDocument()
  })
})
