# syntax=docker/dockerfile:1.7

# ─── BUILDER ──────────────────────────────────────────────────
FROM node:22-alpine AS builder

WORKDIR /app

# Install deps (cached layer)
COPY package.json package-lock.json* ./
RUN npm ci

# Build
COPY . .
RUN npm run build

# ─── RUNTIME (nginx) ──────────────────────────────────────────
FROM nginx:1.27-alpine AS runtime

COPY --from=builder /app/dist /usr/share/nginx/html

# Custom nginx config (SPA routing → fallback to index.html)
RUN echo 'server { \
    listen 80; \
    server_name _; \
    root /usr/share/nginx/html; \
    index index.html; \
    location / { try_files $uri $uri/ /index.html; } \
    location /health { return 200 "ok\\n"; } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -qO- http://localhost/health || exit 1
