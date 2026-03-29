# Deployment Guide

## Prerequisites

- Docker ≥ 24 and Docker Compose plugin
- A domain name (for production)
- A SAML IdP or OIDC provider (e.g. Keycloak, Okta, Azure AD, Google Workspace)
- SMTP server or relay

---

## Quick Start (local development)

```bash
# 1. Clone the repository
git clone https://github.com/vansummeren/music-history-analyser.git
cd music-history-analyser

# 2. Copy and edit the example env file
cp .env.example .env
$EDITOR .env

# 3. Start all services
docker compose up --build

# 4. Open the application
open http://localhost:3000
# API docs: http://localhost:8000/docs
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in all required values before starting the stack.

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | ✅ | Random 32-byte hex string used for token signing and encryption |
| `DATABASE_URL` | ✅ | PostgreSQL DSN, e.g. `postgresql+asyncpg://user:pass@db:5432/musicanalyser` |
| `REDIS_URL` | ✅ | Redis DSN, e.g. `redis://redis:6379/0` |
| `BACKEND_CORS_ORIGINS` | ✅ | Comma-separated allowed origins, e.g. `http://localhost:3000` |
| `AUTH_PROVIDER` | ✅ | `oidc` or `saml` |
| `OIDC_DISCOVERY_URL` | ✅ (OIDC) | Provider discovery document URL |
| `OIDC_CLIENT_ID` | ✅ (OIDC) | Client ID registered with the provider |
| `OIDC_CLIENT_SECRET` | ✅ (OIDC) | Client secret |
| `OIDC_REDIRECT_URI` | ✅ (OIDC, production) | Redirect URI registered with the IdP — must be `https://<your-app>/api/auth/oidc/callback`.  Required behind any reverse proxy. |
| `SAML_IDP_METADATA_URL` | ✅ (SAML) | URL to IdP metadata XML |
| `SAML_SP_ENTITY_ID` | ✅ (SAML) | Service provider entity ID |
| `SAML_SP_ACS_URL` | ✅ (SAML) | Assertion Consumer Service URL |
| `FRONTEND_URL` | ✅ | Public URL of the frontend, e.g. `https://your-app.example.com` |
| `SPOTIFY_CLIENT_ID` | ✅ | Spotify app client ID |
| `SPOTIFY_CLIENT_SECRET` | ✅ | Spotify app client secret |
| `SPOTIFY_REDIRECT_URI` | ✅ | OAuth redirect URI, e.g. `http://localhost:8000/api/spotify/callback` |
| `SMTP_HOST` | ✅ | SMTP host |
| `SMTP_PORT` | ✅ | SMTP port (default `587`) |
| `SMTP_USERNAME` | ✅ | SMTP username |
| `SMTP_PASSWORD` | ✅ | SMTP password |
| `SMTP_FROM` | ✅ | Sender email address |
| `SMTP_TLS` | | `true` / `false` (default `true`) |

### Generating a SECRET_KEY

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

## Production Deployment

### 1. Build & push images (automated via CI)

The GitHub Actions deploy workflow builds images and pushes them to
GitHub Container Registry on every merge to `main`.

Images:
```
ghcr.io/vansummeren/music-history-analyser-backend:<git-sha>
ghcr.io/vansummeren/music-history-analyser-frontend:<git-sha>
```

### 2. Prepare the Docker host

```bash
# On the Docker host
mkdir -p /opt/music-history-analyser
cd /opt/music-history-analyser

# Download the prod compose file
curl -O https://raw.githubusercontent.com/vansummeren/music-history-analyser/main/docker-compose.prod.yml

# Create and fill in the env file
cp .env.example .env
nano .env
```

### 3. Start the stack

```bash
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

### 4. Run database migrations

```bash
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

### 5. Ingress via Cloudflare Tunnel

The stack does not include a Cloudflare Tunnel container. To expose the application:

1. Create a tunnel in the Cloudflare Zero Trust dashboard.
2. Run `cloudflared tunnel run` on the Docker host, pointing to `http://localhost:8000`
   (or the `nginx` frontend container if you front the SPA with nginx).
3. Configure the public hostname in Cloudflare.

---

## Updating

```bash
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

---

## Backup & Restore

### Backup PostgreSQL data

```bash
docker compose -f docker-compose.prod.yml exec db \
  pg_dump -U postgres musicanalyser | gzip > backup_$(date +%Y%m%d).sql.gz
```

### Restore

```bash
gunzip -c backup_20260101.sql.gz | \
  docker compose -f docker-compose.prod.yml exec -T db psql -U postgres musicanalyser
```

---

## Rotating the SECRET_KEY

1. Generate a new `SECRET_KEY`.
2. Update it in the `.env` file.
3. Restart the backend and worker containers.

> ⚠️ Rotating the key invalidates all existing sessions and encrypted tokens stored in the
> database. Users will need to log in again and re-link their Spotify accounts.
