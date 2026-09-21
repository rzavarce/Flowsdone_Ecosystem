import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ThemeProvider } from '@/core/theme/ThemeProvider'
import { THEME_STORAGE_KEY } from '@/core/theme/themes'
import { Logo, type LogoProps } from './Logo'

/** El texto nítido es el <text> sin filtro (en oscuro hay otra capa, aparte, con el resplandor). */
const crisp = (container: HTMLElement) => container.querySelector('text:not([filter])')!

const setup = (props?: LogoProps, mode: 'light' | 'dark' = 'light') => {
  localStorage.setItem(THEME_STORAGE_KEY, JSON.stringify({ theme: 'flowsdone', mode }))
  return render(
    <ThemeProvider>
      <Logo {...props} />
    </ThemeProvider>,
  )
}

describe('Logo', () => {
  it('expone un nombre accesible en cada variante', () => {
    setup({ variant: 'icon' })
    expect(screen.getByRole('img', { name: 'Flowsdone' })).toBeInTheDocument()
  })

  it('wordmark muestra "Flows" + "done" en un solo texto, sin lema', () => {
    const { container } = setup({ variant: 'wordmark' })
    expect(crisp(container).textContent?.replace(/\s+/g, '')).toBe('Flowsdone')
    expect(container.querySelector('tspan')).toHaveTextContent('done')
    expect(screen.queryByText('INTELLIGENCE IN MOTION')).not.toBeInTheDocument()
  })

  it('full agrega el lema y lo refleja en el nombre accesible', () => {
    setup({ variant: 'full' })
    expect(screen.getByText('INTELLIGENCE IN MOTION')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /Intelligence in motion/i })).toBeInTheDocument()
  })

  it('en modo claro el texto es oscuro y no hay resplandor; en oscuro es claro con resplandor', () => {
    const light = setup({ variant: 'wordmark' }, 'light')
    expect(crisp(light.container)).toHaveAttribute('fill', '#04141F')
    expect(light.container.querySelector('[filter]')).toBeNull()
    light.unmount()

    const dark = setup({ variant: 'wordmark' }, 'dark')
    expect(crisp(dark.container)).toHaveAttribute('fill', '#F2FBF7')
    expect(dark.container.querySelector('[filter]')).not.toBeNull()
  })

  it('tone="onDark" fuerza la paleta oscura aunque la app esté en modo claro', () => {
    const { container } = setup({ variant: 'wordmark', tone: 'onDark' }, 'light')
    expect(crisp(container)).toHaveAttribute('fill', '#F2FBF7')
  })

  it('dos logos en la misma página no comparten ids de degradado', () => {
    localStorage.setItem(THEME_STORAGE_KEY, JSON.stringify({ theme: 'flowsdone', mode: 'dark' }))
    const { container } = render(
      <ThemeProvider>
        <Logo variant="icon" />
        <Logo variant="wordmark" />
      </ThemeProvider>,
    )
    const ids = [...container.querySelectorAll('linearGradient')].map((g) => g.id)
    expect(ids).toHaveLength(2)
    expect(new Set(ids).size).toBe(2)
  })
})
