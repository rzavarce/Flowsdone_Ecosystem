import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { ConfirmDialog } from './ConfirmDialog'

function Harness({ requireText, onConfirm = () => {} }: { requireText?: string; onConfirm?: () => void }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button onClick={() => setOpen(true)}>abrir</button>
      <ConfirmDialog open={open} title="Eliminar" description="Cuidado" confirmLabel="Sí, eliminar" requireText={requireText} onConfirm={onConfirm} onCancel={() => setOpen(false)}>
        <p>detalle extra</p>
      </ConfirmDialog>
    </>
  )
}

describe('ConfirmDialog', () => {
  it('sin requireText confirma directamente y muestra el detalle', async () => {
    const onConfirm = vi.fn()
    render(<Harness onConfirm={onConfirm} />)
    await userEvent.click(screen.getByText('abrir'))
    expect(screen.getByText('detalle extra')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Sí, eliminar' }))
    expect(onConfirm).toHaveBeenCalledTimes(1)
  })

  it('con requireText solo se habilita al escribirlo exacto (mayúsculas y espacios cuentan)', async () => {
    render(<Harness requireText="mi-tenant" />)
    await userEvent.click(screen.getByText('abrir'))
    const confirm = screen.getByRole('button', { name: 'Sí, eliminar' })
    const input = screen.getByLabelText('Escribe "mi-tenant" para confirmar')

    expect(confirm).toBeDisabled()
    await userEvent.type(input, 'MI-TENANT')
    expect(confirm).toBeDisabled()
    await userEvent.clear(input)
    await userEvent.type(input, 'mi-tenant ')
    expect(confirm).toBeDisabled()
    await userEvent.clear(input)
    await userEvent.type(input, 'mi-tenant')
    expect(confirm).toBeEnabled()
  })

  it('lo escrito no se arrastra a la siguiente apertura', async () => {
    render(<Harness requireText="x-1" />)
    await userEvent.click(screen.getByText('abrir'))
    await userEvent.type(screen.getByLabelText(/Escribe/), 'x-1')
    await userEvent.click(screen.getByRole('button', { name: 'Cancelar' }))

    await userEvent.click(screen.getByText('abrir'))
    expect(screen.getByLabelText(/Escribe/)).toHaveValue('')
    expect(screen.getByRole('button', { name: 'Sí, eliminar' })).toBeDisabled()
  })
})
