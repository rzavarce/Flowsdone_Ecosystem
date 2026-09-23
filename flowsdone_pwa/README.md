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
  - `admin` (por defecto) — look & feel de [TailAdmin](https://react-demo.tailadmin.com/) (MIT): grises neutros, índigo `#465FFF` como marca/CTA, sidebar y top bar blancos sobre fondo `#F9FAFB` (en oscuro `#101828`), tipografía Outfit.
  - `flowsdone` — identidad de marca "Intelligent Execution": Deep Space `#04141F`, Electric Cyan `#19B4E6`, Neon Flow Green `#3EFF8B`, Soft Ice White `#F2FBF7`, estructura `#11506C`.
  - `agentic` — Violeta & Neón (`#1E1B4B` / `#8B5CF6` / `#10B981`).
  - `corporate` — Azul corporativo & Coral (`#0F172A` / `#2563EB` / `#FF6B6B`).
- **Modo** (clase `dark` en `<html>`): claro, oscuro o del sistema (sigue `prefers-color-scheme` en vivo).

Cada template define, para claro y oscuro, sus neutros y sus colores de marca (`src/index.css`). Reglas de la marca (60-30-10):

- 60 % base: fondo/texto (`--background`, `--foreground`). 30 % estructura: `--primary` (cian) para navegación, gráficos y estados secundarios.
- 10 % acción: `--cta` (verde) **solo** para el botón principal, confirmaciones y estados "hecho" (`--success`).
- `--primary` es para rellenos; para **texto** usar `text-primary-ink` (en claro es un cian más oscuro: el cian puro da 2,3:1 sobre Ice White). Todos los pares texto/fondo se calcularon contra WCAG AA.

La elección se guarda en `localStorage` (`fd-theme`) y un script en `index.html` la aplica antes del primer pintado (sin parpadeo).

La *forma* (sidebar de 290 px con rótulo "Menú", top bar con botones redondos y búsqueda con Ctrl+K, tarjetas planas con borde, campos de 44 px, diálogos amplios, login con panel de marca a la derecha) sigue el estilo TailAdmin en todos los templates; solo cambian los colores. Tokens opcionales por template: `--chrome` (fondo de sidebar/top bar, por defecto `--surface`) e `--input` (borde de campos, por defecto `--border`).

## Idiomas

La consola está en **español (por defecto), catalán e inglés** con i18next + react-i18next (`src/core/i18n/`). Los tres catálogos van empaquetados (funcionan offline en la PWA instalada); `es.ts` es la fuente de las claves y `ca.ts`/`en.ts` están tipados contra él, así que una clave que falte o sobre no compila (y `i18n.test.ts` lo vuelve a comprobar). El idioma se elige en el menú del avatar → **Idioma** (o en el selector de las pantallas de login) y se guarda por navegador (`localStorage` `fd-lang`); `<html lang>` se actualiza con él.

- En componentes: `const { t } = useTranslation()` y `t('seccion.clave')`; plurales con `_one`/`_other` y `{ count }`; texto con marcado con `<Trans>`.
- Catálogos a nivel de módulo (menú, roles, tipos de canal, templates, datos de ejemplo del dashboard): *getters* que llaman a `i18n.t` al leerse. El router se remonta al cambiar de idioma (`key={i18n.language}` en `App.tsx`), así que todo se vuelve a pintar sin perder sesión, tenant ni caché.
- Los tests se escriben contra el español; `src/test/setup.ts` vuelve a `es` después de cada test.

## Perfil de usuario

"Mi perfil" (`/profile`, todos los roles) muestra y edita nombre, teléfono, dirección, redes (sitio web, LinkedIn, X, Facebook, Instagram) y foto, todo opcional salvo el nombre (`PATCH /me/profile`, `PUT|DELETE /me/avatar`). Email, rol y tenants solo los cambia un admin. Los mismos campos se editan en Usuarios (admin). La foto se recorta y reduce a 256 px JPEG en el navegador antes de subirla (`src/lib/resizeImage.ts`); el gateway vuelve a validar el tipo por sus bytes. **Soporte** (`/support`) es por ahora una página de preguntas frecuentes.

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
| `botmaster` | Ve los agentes de sus tenants (solo lectura en `/agentes`; el editor de Langflow es solo del admin). | Agentes |
| `client` | Paneles y gráficos de solo lectura de su organización. | Mi panel |

- La UI pregunta por **permisos**, nunca por roles: `src/core/auth/permissions.ts` (`ROLE_PERMISSIONS`) es la única matriz. Rutas (`RequirePermission`) y menú (`useNavItems`) la consumen.
- **Esto solo controla la visibilidad.** La autorización real debe imponerla el backend en cada endpoint.
- `AuthApi` es el puerto; hay dos adaptadores:
  - `mock` (default en `npm run dev`): cuentas de demostración en memoria, contraseña `demo1234`: `admin@`, `gestor@`, `botmaster@`, `cliente@` `flowsdone.dev`.
  - `http` (default en producción): el gateway real (`/auth/login`, `/auth/me`, `/auth/logout`); la sesión vive en una cookie httpOnly que el frontend nunca ve. En el contenedor nginx reenvía `/api/auth/*` al gateway; en `npm run dev` lo hace el proxy de Vite (`VITE_DEV_API_TARGET`, por defecto `http://localhost:8000`). Los usuarios se crean con el CLI del gateway (ver README raíz).
- Un build de producción usa `http` salvo que se fuerce `VITE_AUTH_MODE=mock`, para que las cuentas demo no lleguen al VPS por accidente.
- Tenant activo: `core/tenant` (`TenantProvider`, `useTenant`) + selector en la barra superior.

## Datos de la API admin

La consola habla con `/internal/admin/*` del gateway a través de `/api/admin/*` (nginx o el proxy de Vite reescriben el prefijo). Solo se exponen los recursos que la UI usa (`tenants`, `projects`, `agents`, `channel-connections`, `channel-apps`, `langflow`); para sumar `users` o `workflows`, agregar el recurso a la lista blanca de `nginx.conf`.

- `core/http/apiFetch.ts`: cliente compartido (cookie, cabecera anti-CSRF, `ApiError` con el `detail` del gateway).
- `core/admin/`: puerto `AdminApi` con adaptador HTTP y **mock** (mismo patrón que la autenticación; con `VITE_AUTH_MODE=mock` no hace falta backend), más hooks de TanStack Query. Un 401 cierra la sesión y la caché se vacía al cambiar de persona.
- El gateway ya devuelve solo lo que el perfil puede ver (rol + tenant); la UI añade el recorte por el tenant activo.

## Canales

`/canales` (admin y gestor): lista, alta, edición y baja de conexiones de canal del tenant activo.

- Cada tipo de canal declara qué necesita (`features/channels/channelTypes.ts`, verificado contra los webhooks/senders del gateway): p. ej. Facebook/Instagram piden el token de la página; Telegram registra el webhook solo.
- El `external_id` de Telegram **es el token del bot**: la UI nunca lo pinta completo.
- Un canal cuelga de un proyecto y su agente debe ser del mismo proyecto (el gateway lo valida). Si el tenant no tiene proyectos, el diálogo permite crear el primero; si el proyecto no tiene agentes, avisa (los agentes se crean en la sección Agentes).
- Al editar no se puede mover de proyecto ni cambiar el identificador (el gateway no lo permite); las credenciales solo se envían si se escriben (vacío = conservar).

## Tenants y proyectos

`/tenants` (admin y gestor), en una sola pantalla: la lista de tenants a la izquierda y, a la derecha, el detalle del elegido con sus proyectos.

- **Admin:** crea, edita, suspende/reactiva y borra tenants, y gestiona sus proyectos. **Gestor:** solo ve sus tenants y gestiona sus proyectos (el gateway lo impone; la UI oculta lo demás).
- **Suspender** (tenant o proyecto) corta el enrutado de sus canales **sin borrar nada**; reactivar es inmediato. El gateway comprueba el estado del canal, del agente, del proyecto **y del tenant** al resolver un mensaje entrante.
- **Borrar es en cascada** (proyectos → agentes → canales). El aviso cuenta lo que hay *ahora* (se piden los datos otra vez antes de mostrarlo, no se usa la caché) y, para un tenant o un proyecto con contenido, hay que **escribir su slug** para confirmar.
- El selector de tenant de la barra superior sale de `/auth/me`, así que tras crear, renombrar o borrar un tenant se vuelve a pedir el usuario (`refreshUser`) y el selector se actualiza solo.

## Agentes y Langflow embebido

`/agentes`: el **admin** elige un tenant en el selector y ve el editor de Langflow embebido, ya con la sesión iniciada como el usuario de ese tenant (solo sus agentes); con «Todos los tenants» pide elegir uno. El resto de perfiles ve la lista de agentes de su tenant, sin editor.

- La URL del iframe la da el gateway (`POST /api/admin/langflow/session` → `url`), con un ticket de un solo uso: por eso `useLangflowSession` no se cachea (`gcTime: 0`) y el iframe se monta con `key={tenantId}` (cada tenant, su ticket). Ya no existe `VITE_LANGFLOW_URL`.
- En modo `mock` no hay Langflow real: se muestra el lienzo de ejemplo.
- Detalles (usuario por tenant, carpeta por proyecto, límites de seguridad) en el README raíz, sección «Langflow embebido por tenant».

## Integraciones de plataforma

En **Ajustes** (solo admin): credenciales de la app compartida de cada proveedor (Meta, X, TikTok, Twilio), que firman los webhooks de *todos* los tenants. Los secretos guardados nunca se muestran ni vuelven al navegador; solo se pueden reemplazar. La única excepción es el token de verificación de Meta (hay que pegarlo en el panel de Meta): se muestra a demanda y se oculta solo a los 30 s.

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

Variables (opcionales, con default en el compose): `PWA_PORT`, `PWA_MEM_LIMIT`, `PWA_CPUS`, `PWA_AUTH_MODE` (`http` | `mock`), `PWA_API_BASE_URL`. Las dos últimas se incrustan en el JS al construir la imagen. Para probar la maqueta en contenedor: `PWA_AUTH_MODE=mock` en el `.env` local (nunca en el VPS).

Estado: **maqueta**. Los datos salen de `src/mocks/data.ts`; la conexión al gateway, la autenticación y la ruta pública en Traefik son features siguientes.
