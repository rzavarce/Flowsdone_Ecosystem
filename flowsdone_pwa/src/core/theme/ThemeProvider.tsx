import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { ThemeContext, type ThemeContextValue } from './ThemeContext'
import {
  THEME_STORAGE_KEY,
  readStoredTheme,
  resolveMode,
  type ColorMode,
  type ThemeId,
} from './themes'

const DARK_QUERY = '(prefers-color-scheme: dark)'

/** Resolves `localStorage`, falling back to `null` if it's unavailable. */
function getStorage(): Storage | null {
  try {
    return window.localStorage
  } catch {
    return null
  }
}

/**
 * Provides the active template and the light/dark mode.
 *
 * Applies `data-theme` and the `dark` class on `<html>` (the `index.css`
 * tokens react to both), persists the choice and follows OS changes while
 * the mode is `system`.
 */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [stored, setStored] = useState(() => readStoredTheme(getStorage()))
  const [systemDark, setSystemDark] = useState(() => window.matchMedia(DARK_QUERY).matches)

  useEffect(() => {
    const query = window.matchMedia(DARK_QUERY)
    const onChange = (event: MediaQueryListEvent) => setSystemDark(event.matches)
    query.addEventListener('change', onChange)
    return () => query.removeEventListener('change', onChange)
  }, [])

  const resolvedMode = resolveMode(stored.mode, systemDark)

  useEffect(() => {
    const root = document.documentElement
    root.dataset.theme = stored.theme
    root.classList.toggle('dark', resolvedMode === 'dark')
  }, [stored.theme, resolvedMode])

  useEffect(() => {
    try {
      getStorage()?.setItem(THEME_STORAGE_KEY, JSON.stringify(stored))
    } catch {
      // Sin storage (modo privado, cuota): el tema vale solo para la sesión.
    }
  }, [stored])

  const setTheme = useCallback((theme: ThemeId) => setStored((s) => ({ ...s, theme })), [])
  const setMode = useCallback((mode: ColorMode) => setStored((s) => ({ ...s, mode })), [])

  const value = useMemo<ThemeContextValue>(
    () => ({ theme: stored.theme, mode: stored.mode, resolvedMode, setTheme, setMode }),
    [stored, resolvedMode, setTheme, setMode],
  )

  return <ThemeContext value={value}>{children}</ThemeContext>
}
