import type { es } from './locales/es'

// Claves tipadas: t('clave.inexistente') no compila.
declare module 'i18next' {
  interface CustomTypeOptions {
    defaultNS: 'translation'
    resources: { translation: typeof es }
  }
}
