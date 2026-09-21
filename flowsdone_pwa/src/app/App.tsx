import { RouterProvider } from 'react-router-dom'
import { ThemeProvider } from '@/core/theme/ThemeProvider'
import { router } from './router'

/** Raíz de la aplicación: proveedores globales + router. */
export function App() {
  return (
    <ThemeProvider>
      <RouterProvider router={router} />
    </ThemeProvider>
  )
}
