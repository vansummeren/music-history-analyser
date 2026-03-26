# syntax=docker/dockerfile:1

# ── build stage ──────────────────────────────────────────────────────────────
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci
COPY . .
RUN npm run build

# ── production stage (nginx) ──────────────────────────────────────────────────
FROM nginx:1.27-alpine AS production
# Remove default nginx user and use an unprivileged one
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
# Ensure nginx can write its pid and cache files as a non-root user
RUN chown -R appuser:appgroup /var/cache/nginx /var/run /var/log/nginx \
    && chmod -R 755 /var/cache/nginx /var/run /var/log/nginx \
    && chown -R appuser:appgroup /usr/share/nginx/html
USER appuser
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
