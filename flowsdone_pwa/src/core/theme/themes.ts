/**
 * Catalog of templates (color presets) and pure helpers for the theme
 * system. No React: it can be tested and reused in the anti-flash script.
 */

/** Identifiers of the available templates. */
export type ThemeId = 'flowsdone' | 'agentic' | 'corporate'

/** Mode preference chosen by the user. */
export type ColorMode = 'light' | 'dark' | 'system'

/** Effective mode once `system` has been resolved. */
export type ResolvedMode = 'light' | 'dark'

/** A template's metadata for display in the selector. */
export interface ThemePreset {
  id: ThemeId
  name: string
  description: string
}

/** Templates in display order. Their colors live in index.css. */
export const THEMES: readonly ThemePreset[] = [
  { id: 'flowsdone', name: 'Flowsdone', description: 'Identidad de marca: Deep Space, cian eléctrico y verde "done".' },
  { id: 'agentic', name: 'Agentic', description: 'Violeta y menta, la estética de las herramientas de agentes.' },
  { id: 'corporate', name: 'Corporate', description: 'Azul cobalto y coral, sobrio para entornos B2B.' },
]

/** Template used when nothing has been chosen yet. */
export const DEFAULT_THEME: ThemeId = 'flowsdone'
/** Color mode used when nothing has been chosen yet: follows the OS. */
export const DEFAULT_MODE: ColorMode = 'system'

/** localStorage key. Must match the anti-flash script in index.html. */
export const THEME_STORAGE_KEY = 'fd-theme'

/** Theme state that gets persisted. */
export interface StoredTheme {
  theme: ThemeId
  mode: ColorMode
}

const THEME_IDS = new Set<string>(THEMES.map((t) => t.id))
const MODES = new Set<string>(['light', 'dark', 'system'])

/**
 * Resolves the effective mode.
 *
 * @param mode - Saved preference (`system` defers to the OS).
 * @param systemPrefersDark - Current value of `prefers-color-scheme: dark`.
 * @returns `light` or `dark`.
 */
export function resolveMode(mode: ColorMode, systemPrefersDark: boolean): ResolvedMode {
  if (mode === 'system') return systemPrefersDark ? 'dark' : 'light'
  return mode
}

/**
 * Reads the persisted theme, tolerating missing storage, broken JSON or
 * values that no longer exist (e.g. a removed preset).
 *
 * @param storage - `localStorage` or a test double; `null` if there is none.
 * @returns The saved theme, defaulting whatever is missing or invalid.
 */
export function readStoredTheme(storage: Pick<Storage, 'getItem'> | null): StoredTheme {
  const fallback: StoredTheme = { theme: DEFAULT_THEME, mode: DEFAULT_MODE }
  if (!storage) return fallback
  try {
    const raw = storage.getItem(THEME_STORAGE_KEY)
    if (!raw) return fallback
    const parsed = JSON.parse(raw) as Partial<StoredTheme> | null
    return {
      theme: parsed && THEME_IDS.has(String(parsed.theme)) ? (parsed.theme as ThemeId) : DEFAULT_THEME,
      mode: parsed && MODES.has(String(parsed.mode)) ? (parsed.mode as ColorMode) : DEFAULT_MODE,
    }
  } catch {
    return fallback
  }
}
