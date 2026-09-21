import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      // Al haber una versión nueva, el service worker se actualiza solo en
      // la próxima carga; más adelante se puede pasar a 'prompt' para avisar.
      registerType: 'autoUpdate',
      includeAssets: ['favicon.svg', 'favicon.ico', 'icons/favicon-32.png', 'icons/apple-touch-icon.png'],
      manifest: {
        name: 'Flowsdone',
        short_name: 'Flowsdone',
        description: 'Consola de la plataforma Flowsdone: agentes, canales y conversaciones.',
        lang: 'es',
        start_url: '/',
        scope: '/',
        display: 'standalone',
        background_color: '#04141f',
        theme_color: '#04141f',
        icons: [
          { src: 'icons/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'icons/icon-512.png', sizes: '512x512', type: 'image/png' },
          {
            src: 'icons/icon-maskable-512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
        ],
      },
      workbox: {
        // SPA: cualquier ruta de navegación cae al index.html precacheado,
        // salvo las del backend, que no deben interceptarse.
        globPatterns: ['**/*.{js,css,html,woff2}'],
        navigateFallback: '/index.html',
        navigateFallbackDenylist: [/^\/api\//, /^\/ws/, /^\/internal\//, /^\/webhooks\//],
      },
    }),
  ],
  resolve: {
    alias: { '@': path.resolve(import.meta.dirname, 'src') },
  },
  server: {
    host: true,
    port: 5173,
    // En desarrollo, /api -> gateway (igual que hace nginx en el contenedor), para
    // que la cookie de sesión sea del mismo origen. Con VITE_AUTH_MODE=mock no se usa.
    proxy: {
      // Más específico primero: /api/admin/* -> /internal/admin/* (como nginx).
      '/api/admin': {
        target: process.env.VITE_DEV_API_TARGET ?? 'http://localhost:8000',
        rewrite: (path) => path.replace(/^\/api\/admin/, '/internal/admin'),
      },
      '/api': {
        target: process.env.VITE_DEV_API_TARGET ?? 'http://localhost:8000',
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
})
