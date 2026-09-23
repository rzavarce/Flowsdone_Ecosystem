import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@/core/i18n/i18n'
import { App } from '@/app/App'
import './index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
