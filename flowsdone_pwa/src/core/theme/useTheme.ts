import { useContext } from 'react'
import { ThemeContext, type ThemeContextValue } from './ThemeContext'

/**
 * Accede al tema activo y a sus setters.
 *
 * @throws Error si se usa fuera de `<ThemeProvider>`.
 */
export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme debe usarse dentro de <ThemeProvider>')
  return ctx
}
