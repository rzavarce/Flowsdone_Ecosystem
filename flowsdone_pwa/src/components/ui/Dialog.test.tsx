import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { Dialog } from './Dialog'

function Harness({ onClose = () => {} }: { onClose?: () => void }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button onClick={() => setOpen(true)}>Abrir</button>
      <Dialog
        open={open}
        onClose={() => {
          onClose()
          setOpen(false)
        }}
        title="Editar canal"
        description="Cambia los datos"
        footer={<button>Guardar</button>}
      >
        <input aria-label="Nombre" />
        <input aria-label="Otro" />
      </Dialog>
    </>
  )
}

describe('Dialog', () => {
  it('no pinta nada cerrado y, abierto, es un diálogo modal con nombre y descripción', async () => {
    render(<Harness />)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    await userEvent.click(screen.getByText('Abrir'))
    const dialog = screen.getByRole('dialog', { name: 'Editar canal' })
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(dialog).toHaveAccessibleDescription('Cambia los datos')
  })

  it('enfoca el primer campo al abrir y devuelve el foco a quien lo abrió al cerrar', async () => {
    render(<Harness />)
    const opener = screen.getByText('Abrir')
    await userEvent.click(opener)
    expect(screen.getByLabelText('Nombre')).toHaveFocus()

    await userEvent.keyboard('{Escape}')
    expect(opener).toHaveFocus()
  })

  it('Escape, la X y hacer clic en el fondo lo cierran', async () => {
    const onClose = vi.fn()
    render(<Harness onClose={onClose} />)

    await userEvent.click(screen.getByText('Abrir'))
    await userEvent.keyboard('{Escape}')
    await userEvent.click(screen.getByText('Abrir'))
    await userEvent.click(screen.getByRole('button', { name: 'Cerrar' }))
    await userEvent.click(screen.getByText('Abrir'))
    await userEvent.click(screen.getByRole('dialog').parentElement!) // el fondo
    expect(onClose).toHaveBeenCalledTimes(3)
  })

  it('hacer clic dentro del panel no lo cierra', async () => {
    const onClose = vi.fn()
    render(<Harness onClose={onClose} />)
    await userEvent.click(screen.getByText('Abrir'))
    await userEvent.click(screen.getByLabelText('Otro'))
    expect(onClose).not.toHaveBeenCalled()
  })

  it('el foco queda atrapado: Tab desde el último vuelve al primero y Shift+Tab al revés', async () => {
    render(<Harness />)
    await userEvent.click(screen.getByText('Abrir'))
    const guardar = screen.getByRole('button', { name: 'Guardar' })

    guardar.focus()
    await userEvent.tab()
    expect(screen.getByRole('button', { name: 'Cerrar' })).toHaveFocus() // primer elemento enfocable

    await userEvent.tab({ shift: true })
    expect(guardar).toHaveFocus() // envuelve al último
  })

  it('bloquea el scroll del fondo mientras está abierto y lo restaura', async () => {
    render(<Harness />)
    await userEvent.click(screen.getByText('Abrir'))
    expect(document.body.style.overflow).toBe('hidden')
    await userEvent.keyboard('{Escape}')
    expect(document.body.style.overflow).toBe('')
  })
})
