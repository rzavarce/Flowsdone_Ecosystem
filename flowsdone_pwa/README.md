# flowsdone_pwa

Consola web (PWA) de la plataforma Flowsdone. React + TypeScript, servida por nginx como un servicio más del `docker-compose.yml` (`pwa`).

## Stack y por qué

| Pieza | Elección | Motivo |
|---|---|---|
| Build | Vite | Arranque y HMR rápidos; salida estática simple de servir con nginx. |
| UI | React 19 + TypeScript | — |
| Estilos | Tailwind CSS v4 + tokens CSS | Los colores son variables; cambiar de template no toca componentes. |
| Iconos | lucide-react | Ligeros, tree-shakeable. |
| Rutas | react-router-dom | — |
| PWA | vite-plugin-pwa (Workbox) | Manifest + service worker autogenerados, precache del shell. |
| Tests | Vitest + Testing Library | Mismo pipeline que Vite. |

No se usó una librería de componentes completa (MUI, Ant…): los componentes base (`components/ui`) son pocos y propios, para que el template dinámico se aplique de forma uniforme.

## Template dinámico

El aspecto se controla con dos ejes independientes, ambos desde **Ajustes → Apariencia**:

- **Template** (`data-theme` en `<html>`): `aurora`, `ocean`, `sunset`, `emerald`. Cada uno solo define dos colores de marca (`--primary`, `--primary-2`); acentos y gradientes se derivan con `color-mix`.
- **Modo** (clase `dark` en `<html>`): claro, oscuro o del sistema (sigue `prefers-color-scheme` en vivo).

La elección se guarda en `localStorage` (`fd-theme`) y un script en `index.html` la aplica antes del primer pintado para evitar el parpadeo.

**Agregar un template nuevo:** un bloque `[data-theme='x']` (y su variante `.dark`) en `src/index.css` + una entrada en `THEMES` (`src/core/theme/themes.ts`) + el id en el script anti-flash de `index.html`.

## Estructura

```
src/
  app/            App, router
  core/theme/     ThemeProvider, useTheme, catálogo de templates
  components/
    ui/           Button, Card, Badge, Avatar, Input, EmptyState
    layout/       AppShell, Sidebar, Topbar, MobileNav, PageHeader, navigation
    theme/        ModeToggle, ThemePicker
  features/       una carpeta por sección (dashboard, channels, conversations, workflows, settings)
  lib/            utilidades puras (cn, format, initials)
  mocks/          datos de ejemplo de la maqueta
```

Regla: las `features` dependen de `components`/`core`/`lib`, nunca entre sí.

## Desarrollo

```bash
npm install
npm run dev        # http://localhost:5173
npm test           # vitest
npm run typecheck
npm run lint
npm run build      # genera dist/ con manifest + service worker
```

## Docker

```bash
docker compose --profile dev up -d --build pwa   # http://localhost:${PWA_PORT:-3000}
```

Variables (opcionales, con default en el compose): `PWA_PORT`, `PWA_MEM_LIMIT`, `PWA_CPUS`.

Estado: **maqueta**. Los datos salen de `src/mocks/data.ts`; la conexión al gateway, la autenticación y la ruta pública en Traefik son features siguientes.
