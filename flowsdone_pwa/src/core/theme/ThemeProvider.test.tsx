import { act, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ThemeProvider } from './ThemeProvider'
import { THEME_STORAGE_KEY } from './themes'
import { useTheme } from './useTheme'

function Probe() {
  const { theme, mode, resolvedMode, setTheme, setMode } = useTheme()
  return (
    <div>
      <span data-testid="state">{`${theme}|${mode}|${resolvedMode}`}</span>
      <button onClick={() => setTheme('agentic')}>agentic</button>
      <button onClick={() => setMode('dark')}>dark</button>
      <button onClick={() => setMode('system')}>system</button>
    </div>
  )
}

/** Simula matchMedia con un valor inicial y permite disparar cambios. */
function mockSystemDark(initial: boolean) {
  let listener: ((e: MediaQueryListEvent) => void) | null = null
  vi.stubGlobal('matchMedia', () => ({
    matches: initial,
    addEventListener: (_: string, cb: (e: MediaQueryListEvent) => void) => (listener = cb),
    removeEventListener: () => (listener = null),
  }))
  return (matches: boolean) => listener?.({ matches } as MediaQueryListEvent)
}

afterEach(() => vi.unstubAllGlobals())

describe('ThemeProvider', () => {
  it('arranca con aurora + system y refleja el SO claro', () => {
    mockSystemDark(false)
    render(<ThemeProvider><Probe /></ThemeProvider>)
    expect(screen.getByTestId('state')).toHaveTextContent('flowsdone|system|light')
    expect(document.documentElement.dataset.theme).toBe('flowsdone')
    expect(document.documentElement).not.toHaveClass('dark')
  })

  it('aplica data-theme y la clase dark al cambiar y lo persiste', () => {
    mockSystemDark(false)
    render(<ThemeProvider><Probe /></ThemeProvider>)

    act(() => screen.getByText('agentic').click())
    act(() => screen.getByText('dark').click())

    expect(document.documentElement.dataset.theme).toBe('agentic')
    expect(document.documentElement).toHaveClass('dark')
    expect(JSON.parse(localStorage.getItem(THEME_STORAGE_KEY)!)).toEqual({ theme: 'agentic', mode: 'dark' })
  })

  it('restaura la elección guardada', () => {
    mockSystemDark(false)
    localStorage.setItem(THEME_STORAGE_KEY, JSON.stringify({ theme: 'corporate', mode: 'dark' }))
    render(<ThemeProvider><Probe /></ThemeProvider>)
    expect(screen.getByTestId('state')).toHaveTextContent('corporate|dark|dark')
  })

  it('en system sigue los cambios del SO en vivo', () => {
    const emit = mockSystemDark(false)
    render(<ThemeProvider><Probe /></ThemeProvider>)

    act(() => emit(true))
    expect(screen.getByTestId('state')).toHaveTextContent('flowsdone|system|dark')
    expect(document.documentElement).toHaveClass('dark')
  })
})

describe('useTheme', () => {
  it('falla con un mensaje claro fuera del provider', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    expect(() => render(<Probe />)).toThrow(/ThemeProvider/)
    spy.mockRestore()
  })
})
