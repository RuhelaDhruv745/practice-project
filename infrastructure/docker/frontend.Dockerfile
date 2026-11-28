# React + Vite frontend image: build static files, serve them with unprivileged nginx.
# Build from the repo root:
#   docker build -f infrastructure/docker/frontend.Dockerfile \
#     --build-arg VITE_API_BASE_URL=http://localhost:8000 .
# VITE_API_BASE_URL is compiled into the bundle and must be the URL the *browser* uses
# to reach the backend. It is a public URL, never a secret.

# ---- build stage ----
FROM node:22-alpine AS build

ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- runtime stage: static files only, non-root nginx on 8080 ----
FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime

COPY infrastructure/docker/nginx-frontend.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/frontend/dist /usr/share/nginx/html

EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
    CMD wget -q --spider http://127.0.0.1:8080/ || exit 1
