import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { Alert } from './Alert'

describe('Alert', () => {
  it('un tono danger se anuncia como alert; el resto como status', () => {
    const { rerender } = render(<Alert tone="danger">x</Alert>)
    expect(screen.getByRole('alert')).toHaveTextContent('x')

    rerender(<Alert tone="success">y</Alert>)
    expect(screen.getByRole('status')).toHaveTextContent('y')
  })

  it('sin onDismiss no muestra botón de quitar', () => {
    render(<Alert tone="info">x</Alert>)
    expect(screen.queryByRole('button', { name: 'Quitar aviso' })).not.toBeInTheDocument()
  })

  it('con onDismiss muestra el botón y lo llama al hacer click', async () => {
    const onDismiss = vi.fn()
    render(<Alert tone="success" onDismiss={onDismiss}>x</Alert>)
    await userEvent.click(screen.getByRole('button', { name: 'Quitar aviso' }))
    expect(onDismiss).toHaveBeenCalledOnce()
  })
})
