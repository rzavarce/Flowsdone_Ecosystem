import { describe, expect, it } from 'vitest'
import { summarize } from './useTenantsView'

describe('summarize', () => {
  it('usa singular y plural correctos', () => {
    expect(summarize({ projects: 1, agents: 1, channels: 1 })).toBe('1 proyecto · 1 agente · 1 canal')
    expect(summarize({ projects: 2, agents: 3, channels: 0 })).toBe('2 proyectos · 3 agentes · 0 canales')
  })

  it('sin proyectos (recuento de un proyecto) omite esa parte', () => {
    expect(summarize({ agents: 2, channels: 1 })).toBe('2 agentes · 1 canal')
  })
})
