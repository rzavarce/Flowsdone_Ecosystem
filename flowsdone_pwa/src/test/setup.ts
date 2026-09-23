import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'
import { cleanup, configure } from '@testing-library/react'
// Los tests se escriben contra los textos en español (el idioma por defecto).
import { i18n } from '@/core/i18n/i18n'

// Con la suite completa en paralelo, jsdom va lento y pantallas que cargan
// varias consultas (Tenants, Conversaciones) superan a veces el segundo por
// defecto de findBy*/waitFor: fallos intermitentes, no reales.
configure({ asyncUtilTimeout: 3000 })

afterEach(() => {
  cleanup()
  void i18n.changeLanguage('es')
  localStorage.clear()
  document.documentElement.className = ''
  document.documentElement.removeAttribute('data-theme')
  fullscreenState.element = null
})

// jsdom no implementa la Fullscreen API (sus métodos existen en los tipos de
// TypeScript, pero no en tiempo de ejecución). Se simula sobre un solo
// elemento "en pantalla completa" a la vez (como el navegador) y disparando
// `fullscreenchange`, que es lo que consume LangflowEmbed. Se pisa como
// `any` porque `document.fullscreenElement` es de solo lectura.
const fullscreenState: { element: Element | null } = { element: null }
if (typeof document.exitFullscreen !== 'function') {
  Object.defineProperty(document, 'fullscreenElement', { get: () => fullscreenState.element })
  document.exitFullscreen = async () => {
    fullscreenState.element = null
    document.dispatchEvent(new Event('fullscreenchange'))
  }
  Element.prototype.requestFullscreen = async function (this: Element) {
    fullscreenState.element = this
    document.dispatchEvent(new Event('fullscreenchange'))
  }
}

// jsdom no implementa matchMedia; los tests lo pisan cuando necesitan
// simular prefers-color-scheme.
if (!window.matchMedia) {
  window.matchMedia = (query: string) =>
    ({
      matches: false,
      media: query,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
      onchange: null,
    }) as MediaQueryList
}
