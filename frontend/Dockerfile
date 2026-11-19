# syntax=docker/dockerfile:1
# Builds the React app and serves it with Caddy, which also terminates TLS and
# proxies /api to the Flask backend. Build context: repository root.
FROM node:26-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM caddy:2-alpine
COPY deploy/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/dist /srv
