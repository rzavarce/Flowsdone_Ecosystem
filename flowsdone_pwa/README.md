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

El aspecto se controla con dos ejes independientes, desde **Ajustes → Apariencia**:

- **Template** (`data-theme` en `<html>`):
  - `flowsdone` (por defecto) — identidad de marca "Intelligent Execution": Deep Space `#04141F`, Electric Cyan `#19B4E6`, Neon Flow Green `#3EFF8B`, Soft Ice White `#F2FBF7`, estructura `#11506C`.
  - `agentic` — Violeta & Neón (`#1E1B4B` / `#8B5CF6` / `#10B981`).
  - `corporate` — Azul corporativo & Coral (`#0F172A` / `#2563EB` / `#FF6B6B`).
- **Modo** (clase `dark` en `<html>`): claro, oscuro o del sistema (sigue `prefers-color-scheme` en vivo).

Cada template define, para claro y oscuro, sus neutros y sus colores de marca (`src/index.css`). Reglas de la marca (60-30-10):

- 60 % base: fondo/texto (`--background`, `--foreground`). 30 % estructura: `--primary` (cian) para navegación, gráficos y estados secundarios.
- 10 % acción: `--cta` (verde) **solo** para el botón principal, confirmaciones y estados "hecho" (`--success`).
- `--primary` es para rellenos; para **texto** usar `text-primary-ink` (en claro es un cian más oscuro: el cian puro da 2,3:1 sobre Ice White). Todos los pares texto/fondo se calcularon contra WCAG AA.

La elección se guarda en `localStorage` (`fd-theme`) y un script en `index.html` la aplica antes del primer pintado (sin parpadeo).

**Agregar un template:** bloque claro + bloque `.dark` en `src/index.css`, una entrada en `THEMES` (`src/core/theme/themes.ts`) y el id en el script anti-flash de `index.html`.

## Logo y assets de marca

Fuente de verdad del diseño: `public/brand/flowsdone-logo.svg` (lockup sobre Deep Space).

| Archivo | Uso |
|---|---|
| `public/brand/flowsdone-logo.svg` | Lockup con lema, fondo oscuro (redes, presentaciones). |
| `public/brand/flowsdone-logo-light.svg` | Mismo lockup, sin fondo y con colores para fondos **claros**. |
| `public/brand/flowsdone-mark.svg`, `public/favicon.svg` | Isotipo cuadrado (la onda que termina en "check"). |
| `public/favicon.ico`, `icons/favicon-32.png` | Favicons (16/32/48). |
| `public/icons/icon-192/512.png`, `icon-maskable-512.png`, `apple-touch-icon.png` | Iconos de la PWA / iOS. |

En la UI se usa el componente `components/layout/Logo` (`icon` | `wordmark` | `full`, tono `auto` | `onDark`), que pinta el mismo trazo como SVG en línea y adapta los colores al modo claro/oscuro. Si cambia el diseño del logo hay que actualizar `Logo.tsx` y regenerar los PNG desde `flowsdone-mark.svg`.

## Rutas

- `/` → sin sesión, `/login`; con sesión, la página de inicio del perfil.
- `/login` → pública. Tras autenticar va al destino que se intentó abrir o, si no lo hay, a `/dashboard` (o `/agentes` para el botmaster).
- `/dashboard`, `/conversaciones`, `/canales`, `/agentes`, `/ajustes` → exigen sesión y el permiso de cada sección.

## Autenticación y perfiles

| Perfil | Alcance | Inicio |
|---|---|---|
| `admin` | Todo, en todos los tenants (incluye "Todos los tenants"). | Dashboard |
| `tenant_manager` | Todo, pero solo en sus tenants asignados. | Dashboard |
| `botmaster` | Solo crear/editar agentes (Langflow embebido, `/agentes`). | Agentes |
| `client` | Paneles y gráficos de solo lectura de su organización. | Mi panel |

- La UI pregunta por **permisos**, nunca por roles: `src/core/auth/permissions.ts` (`ROLE_PERMISSIONS`) es la única matriz. Rutas (`RequirePermission`) y menú (`useNavItems`) la consumen.
- **Esto solo controla la visibilidad.** La autorización real debe imponerla el backend en cada endpoint.
- `AuthApi` es el puerto; hay dos adaptadores:
  - `mock` (default en `npm run dev`): cuentas de demostración en memoria, contraseña `demo1234`: `admin@`, `gestor@`, `botmaster@`, `cliente@` `flowsdone.dev`.
  - `http` (default en producción): el gateway real (`/auth/login`, `/auth/me`, `/auth/logout`); la sesión vive en una cookie httpOnly que el frontend nunca ve. En el contenedor nginx reenvía `/api/auth/*` al gateway; en `npm run dev` lo hace el proxy de Vite (`VITE_DEV_API_TARGET`, por defecto `http://localhost:8000`). Los usuarios se crean con el CLI del gateway (ver README raíz).
- Un build de producción usa `http` salvo que se fuerce `VITE_AUTH_MODE=mock`, para que las cuentas demo no lleguen al VPS por accidente.
- Tenant activo: `core/tenant` (`TenantProvider`, `useTenant`) + selector en la barra superior.

## Estructura

```
src/
  app/            App, router
  core/theme/     ThemeProvider, useTheme, catálogo de templates
  core/auth/      tipos, permisos, puerto AuthApi, adaptadores mock/http, AuthProvider
  core/tenant/    tenant activo
  components/
    ui/           Button, Card, Badge, Avatar, Input, EmptyState, Spinner
    auth/         RequireAuth, PublicOnly, RequirePermission (guards de ruta)
    charts/       StatCard, ActivityChart
    layout/       AppShell, Sidebar, Topbar, MobileNav, PageHeader, navigation
    theme/        ModeToggle, ThemePicker
  features/       una carpeta por sección (auth, dashboard, reports, channels, conversations, agents, settings)
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

# Maqueta con cuentas de demostración (sin backend de auth):
PWA_AUTH_MODE=mock docker compose --profile dev up -d --build pwa
```

Variables (opcionales, con default en el compose): `PWA_PORT`, `PWA_MEM_LIMIT`, `PWA_CPUS`, `PWA_AUTH_MODE` (`http` | `mock`), `PWA_API_BASE_URL`, `PWA_LANGFLOW_URL`. Las tres últimas se incrustan en el JS al construir la imagen. Para probar la maqueta en contenedor: `PWA_AUTH_MODE=mock` en el `.env` local (nunca en el VPS).

Estado: **maqueta**. Los datos salen de `src/mocks/data.ts`; la conexión al gateway, la autenticación y la ruta pública en Traefik son features siguientes.
