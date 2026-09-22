# syntax=docker/dockerfile:1

# ---- build: compila la SPA con Vite ----------------------------------
FROM node:22-alpine AS build
WORKDIR /app

# Primero solo los manifests: la capa de `npm ci` se cachea mientras no
# cambien las dependencias.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Vite incrusta estas variables en el bundle en tiempo de build (no son secretos:
# quedan visibles en el JS). VITE_AUTH_MODE=mock habilita las cuentas de
# demostración: usarlo SOLO en maquetas locales, nunca en producción.
ARG VITE_AUTH_MODE=http
ARG VITE_API_BASE_URL=/api
ENV VITE_AUTH_MODE=$VITE_AUTH_MODE \
    VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

# ---- runtime: nginx sirve el estático --------------------------------
FROM nginx:1.27-alpine AS runtime
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1/healthz || exit 1
