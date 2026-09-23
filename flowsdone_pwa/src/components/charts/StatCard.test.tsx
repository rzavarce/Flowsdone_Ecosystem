import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { StatCard } from './StatCard'

describe('StatCard', () => {
  it('muestra etiqueta, valor y tendencia al alza con su contexto accesible', () => {
    render(<StatCard stat={{ id: 'conversations', label: 'Conversaciones hoy', value: '1.284', delta: 12.4 }} />)
    expect(screen.getByText('Conversaciones hoy')).toBeInTheDocument()
    expect(screen.getByText('1.284')).toBeInTheDocument()
    expect(screen.getByText(/frente a la semana anterior/)).toBeInTheDocument()
  })

  it('una caída se pinta con el tono danger', () => {
    render(<StatCard stat={{ id: 'response', label: 'Tiempo', value: '1,8 s', delta: -14.2 }} />)
    expect(screen.getByText(/frente a la semana anterior/).parentElement).toHaveClass('text-danger')
  })

  it('un id desconocido no rompe: usa el icono genérico', () => {
    const { container } = render(<StatCard stat={{ id: 'otro', label: 'X', value: '1', delta: 0 }} />)
    expect(container.querySelector('svg')).not.toBeNull()
  })
})
