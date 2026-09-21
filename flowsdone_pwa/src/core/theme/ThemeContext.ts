import { createContext } from 'react'
import type { ColorMode, ResolvedMode, ThemeId } from './themes'

/** Valor expuesto por {@link ThemeProvider}. */
export interface ThemeContextValue {
  theme: ThemeId
  mode: ColorMode
  resolvedMode: ResolvedMode
  setTheme: (theme: ThemeId) => void
  setMode: (mode: ColorMode) => void
}

export const ThemeContext = createContext<ThemeContextValue | null>(null)
