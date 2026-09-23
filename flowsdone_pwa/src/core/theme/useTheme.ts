import { useContext } from 'react'
import { ThemeContext, type ThemeContextValue } from './ThemeContext'

/**
 * Accesses the active theme and its setters.
 *
 * @throws Error if used outside `<ThemeProvider>`.
 */
export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme debe usarse dentro de <ThemeProvider>')
  return ctx
}
