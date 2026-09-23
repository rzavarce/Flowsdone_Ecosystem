import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import { ca } from './locales/ca'
import { en } from './locales/en'
import { es } from './locales/es'

/**
 * Internationalization: i18next + react-i18next with the three console
 * languages bundled (no network fetch, works offline in the installed PWA).
 * Spanish is the default and the fallback for any missing key. The choice is
 * per browser (localStorage), like the theme.
 */

/** Supported languages. */
export type Language = 'es' | 'ca' | 'en'

/** Languages in display order, with their own-language name for the selector. */
export const LANGUAGES: readonly { id: Language; name: string; short: string }[] = [
  { id: 'es', name: 'Español', short: 'ES' },
  { id: 'ca', name: 'Català', short: 'CA' },
  { id: 'en', name: 'English', short: 'EN' },
]

/** Language used when nothing has been chosen yet. */
export const DEFAULT_LANGUAGE: Language = 'es'

/** localStorage key of the chosen language. */
export const LANGUAGE_STORAGE_KEY = 'fd-lang'

const IDS = new Set<string>(LANGUAGES.map((l) => l.id))

/**
 * Reads the persisted language, tolerating missing storage or unknown values.
 *
 * @param storage - `localStorage` or a test double; `null` if there is none.
 * @returns The saved language, or {@link DEFAULT_LANGUAGE}.
 */
export function readStoredLanguage(storage: Pick<Storage, 'getItem'> | null): Language {
  try {
    const value = storage?.getItem(LANGUAGE_STORAGE_KEY)
    return value && IDS.has(value) ? (value as Language) : DEFAULT_LANGUAGE
  } catch {
    return DEFAULT_LANGUAGE
  }
}

/** `localStorage`, or `null` where it's unavailable (private mode, SSR). */
function safeStorage(): Storage | null {
  try {
    return window.localStorage
  } catch {
    return null
  }
}

void i18n.use(initReactI18next).init({
  resources: { es: { translation: es }, ca: { translation: ca }, en: { translation: en } },
  lng: readStoredLanguage(safeStorage()),
  fallbackLng: DEFAULT_LANGUAGE,
  interpolation: { escapeValue: false }, // React ya escapa.
  initAsync: false,
})
document.documentElement.lang = i18n.language

/**
 * Switches the UI language, persists it and updates `<html lang>`.
 *
 * @param language - The language to switch to.
 */
export function setLanguage(language: Language): void {
  void i18n.changeLanguage(language)
  document.documentElement.lang = language
  try {
    safeStorage()?.setItem(LANGUAGE_STORAGE_KEY, language)
  } catch {
    // Sin storage el idioma vale solo hasta recargar.
  }
}

/** The active language (narrowed to {@link Language}). */
export function currentLanguage(): Language {
  return IDS.has(i18n.language) ? (i18n.language as Language) : DEFAULT_LANGUAGE
}

/** BCP 47 locale for `Intl` formatting in the active language. */
export function currentLocale(): string {
  return { es: 'es-ES', ca: 'ca-ES', en: 'en-GB' }[currentLanguage()]
}

export { i18n }
