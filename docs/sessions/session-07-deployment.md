# Session 07 — Production Hardening & Deployment

## Goal
Prepare the application for production deployment: hardened Docker images, production
Compose file, deploy pipeline (push to GHCR), and finalised documentation.

## Prerequisite
Sessions 01–06 completed and merged.

## Scope

### Docker hardening
- Multi-stage `Dockerfile` for backend (build → slim runtime image)
- Multi-stage `Dockerfile` for frontend (build → nginx static serving)
- Non-root user in all images
- Read-only root filesystem where possible
- Health checks in `docker-compose.yml`

### `docker-compose.prod.yml`
- No exposed ports except the backend (or nginx) port — let Cloudflare Tunnel / reverse proxy
  handle ingress
- Named volumes for Postgres data
- `restart: unless-stopped` on all services
- Resource limits (memory, CPU)
- Secrets passed via environment (document expected env vars)

### GitHub Actions deploy workflow
- Trigger: push to `main` after CI passes
- Build and tag images: `ghcr.io/<owner>/music-history-analyser-backend:<sha>` and `…-frontend:<sha>`
- Push to GitHub Container Registry
- Optionally trigger a deploy webhook (URL configured as a GitHub secret)

### Security review
- Dependency audit (`pip-audit`, `npm audit`)
- OWASP headers via FastAPI middleware (HSTS, X-Frame-Options, CSP, etc.)
- Ensure `SECRET_KEY` rotation procedure is documented
- Rate limiting on sensitive endpoints
- Confirm CORS configuration is tight in production

### Documentation
- `docs/deployment.md` (complete)
- `docs/api.md` (complete, generated from OpenAPI spec)
- `README.md` (badges, quick-start, env var reference)

## Acceptance Criteria
- `docker compose -f docker-compose.prod.yml up` starts cleanly
- Images are published to GHCR on a push to `main`
- `pip-audit` reports no known vulnerabilities
- `npm audit` reports no high/critical vulnerabilities
- OWASP security headers present in responses
- All previous tests still pass

## Key Files to Create / Modify

```
backend/
  Dockerfile          (multi-stage)
  app/middleware.py   (security headers)
  pyproject.toml      (add pip-audit tooling)

frontend/
  Dockerfile          (multi-stage with nginx)
  nginx.conf

docker-compose.prod.yml
.github/workflows/deploy.yml
docs/deployment.md   (complete)
docs/api.md          (complete)
README.md            (badges + full quick-start)
```
