/**
 * Catálogo de templates (presets de color) y helpers puros del sistema de
 * temas. Sin React: se puede testear y reutilizar en el script anti-flash.
 */

/** Identificadores de los presets disponibles. */
export type ThemeId = 'aurora' | 'ocean' | 'sunset' | 'emerald'

/** Preferencia de modo elegida por la persona usuaria. */
export type ColorMode = 'light' | 'dark' | 'system'

/** Modo efectivo una vez resuelto `system`. */
export type ResolvedMode = 'light' | 'dark'

/** Metadatos de un preset para mostrarlo en el selector. */
export interface ThemePreset {
  id: ThemeId
  name: string
  description: string
}

/** Presets en el orden en que se muestran. Los colores viven en index.css. */
export const THEMES: readonly ThemePreset[] = [
  { id: 'aurora', name: 'Aurora', description: 'Índigo y violeta, el look por defecto.' },
  { id: 'ocean', name: 'Ocean', description: 'Azul y turquesa, sobrio y técnico.' },
  { id: 'sunset', name: 'Sunset', description: 'Naranja y rosa, cálido y llamativo.' },
  { id: 'emerald', name: 'Emerald', description: 'Verde esmeralda, fresco y limpio.' },
]

export const DEFAULT_THEME: ThemeId = 'aurora'
export const DEFAULT_MODE: ColorMode = 'system'

/** Clave de localStorage. Debe coincidir con el script anti-flash de index.html. */
export const THEME_STORAGE_KEY = 'fd-theme'

/** Estado de tema que se persiste. */
export interface StoredTheme {
  theme: ThemeId
  mode: ColorMode
}

const THEME_IDS = new Set<string>(THEMES.map((t) => t.id))
const MODES = new Set<string>(['light', 'dark', 'system'])

/**
 * Resuelve el modo efectivo.
 *
 * @param mode - Preferencia guardada (`system` delega en el SO).
 * @param systemPrefersDark - Valor actual de `prefers-color-scheme: dark`.
 * @returns `light` o `dark`.
 */
export function resolveMode(mode: ColorMode, systemPrefersDark: boolean): ResolvedMode {
  if (mode === 'system') return systemPrefersDark ? 'dark' : 'light'
  return mode
}

/**
 * Lee el tema persistido, tolerando storage ausente, JSON roto o valores
 * que ya no existen (p. ej. un preset eliminado).
 *
 * @param storage - `localStorage` o un doble de test; `null` si no hay.
 * @returns El tema guardado, con defaults en lo que falte o sea inválido.
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
