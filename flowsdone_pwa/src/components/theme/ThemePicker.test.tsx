import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { ThemeProvider } from '@/core/theme/ThemeProvider'
import { THEMES } from '@/core/theme/themes'
import { ThemePicker } from './ThemePicker'

const setup = () =>
  render(
    <ThemeProvider>
      <ThemePicker />
    </ThemeProvider>,
  )

describe('ThemePicker', () => {
  it('lista un radio por cada preset del catálogo', () => {
    setup()
    for (const preset of THEMES) {
      expect(screen.getByRole('radio', { name: new RegExp(preset.name) })).toBeInTheDocument()
    }
  })

  it('marca admin (estilo TailAdmin) como activo por defecto', () => {
    setup()
    expect(screen.getByRole('radio', { name: /Admin/ })).toBeChecked()
    expect(screen.getByRole('radio', { name: /Flowsdone/ })).not.toBeChecked()
  })

  it('cambia el template activo y el data-theme del documento', async () => {
    setup()
    await userEvent.click(screen.getByRole('radio', { name: /Agentic/ }))
    expect(screen.getByRole('radio', { name: /Agentic/ })).toBeChecked()
    expect(screen.getByRole('radio', { name: /Admin/ })).not.toBeChecked()
    expect(document.documentElement.dataset.theme).toBe('agentic')
  })

  it('cambia el modo a oscuro', async () => {
    setup()
    await userEvent.click(screen.getByRole('radio', { name: 'Oscuro' }))
    expect(document.documentElement).toHaveClass('dark')
  })
})
