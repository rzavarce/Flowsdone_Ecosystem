import { createContext } from 'react'
import type { ColorMode, ResolvedMode, ThemeId } from './themes'

/** Value exposed by {@link ThemeProvider}. */
export interface ThemeContextValue {
  theme: ThemeId
  mode: ColorMode
  resolvedMode: ResolvedMode
  setTheme: (theme: ThemeId) => void
  setMode: (mode: ColorMode) => void
}

/** React context carrying the current {@link ThemeContextValue}; `null` outside `<ThemeProvider>`. */
export const ThemeContext = createContext<ThemeContextValue | null>(null)
