# Music History Analyser

[![CI](https://github.com/vansummeren/music-history-analyser/actions/workflows/ci.yml/badge.svg)](https://github.com/vansummeren/music-history-analyser/actions/workflows/ci.yml)
[![Deploy](https://github.com/vansummeren/music-history-analyser/actions/workflows/deploy.yml/badge.svg)](https://github.com/vansummeren/music-history-analyser/actions/workflows/deploy.yml)

Analyse your Spotify listening history with AI. Connect your Spotify account, choose an AI
provider (Claude, Perplexity, …), write a custom prompt, and schedule recurring analyses that
land in your inbox.

---

## Quick Start (local development)

### Prerequisites

- Docker ≥ 24 and the Docker Compose plugin
- An OIDC or SAML identity provider (see [Authentication setup](#authentication-setup) below)
- Spotify developer application (for Spotify integration)
- An SMTP server for email delivery

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/vansummeren/music-history-analyser.git
cd music-history-analyser

# 2. Configure environment — fill in every required value
cp .env.example .env
$EDITOR .env

# 3. Start all services (database, Redis, backend, worker, frontend)
docker compose up --build

# 4. In a separate terminal, apply database migrations
docker compose exec backend alembic upgrade head
```

- **Frontend**: http://localhost:3000  
- **API interactive docs**: http://localhost:8000/docs

> The Vite dev-server proxies all `/api` requests to the backend container via Docker
> service-name DNS (`http://backend:8000`).  No additional reverse-proxy setup is needed
> for local development.

---

## Authentication setup

The application delegates authentication entirely to an external identity provider —
there are no local username/password accounts.

### Choosing a provider

Set `AUTH_PROVIDER` in `.env` to one of:

| Value | Protocol | When to use |
|---|---|---|
| `oidc` | OpenID Connect | Most modern IdPs (Authentik, Keycloak, Okta, Azure AD, Google) |
| `saml` | SAML 2.0 | Enterprise environments requiring SAML |

See [docs/idp-configuration.md](docs/idp-configuration.md) for full per-IdP setup
instructions, flow diagrams, and a production checklist.

### Essential variables

| Variable | When required | Description |
|---|---|---|
| `FRONTEND_URL` | Always | Public URL of the frontend, e.g. `https://your-app.example.com`.  Used to build the post-login redirect. |
| `OIDC_REDIRECT_URI` | OIDC in production | The exact redirect URI registered with your IdP — `https://<your-app>/api/auth/oidc/callback`. **Required behind any reverse proxy.** |
| `SAML_SP_ACS_URL` | SAML | The Assertion Consumer Service URL — `https://<your-app>/api/auth/saml/acs`. |
| `SAML_SP_ENTITY_ID` | SAML | Service provider entity ID / issuer — typically the app's root URL. |

### Post-login token flow

After a successful IdP login the backend issues two tokens and redirects the browser to
`{FRONTEND_URL}/auth/callback#access_token=…&refresh_token=…`.

The `AuthCallbackPage` React component extracts the tokens from the URL fragment (they
never appear in server logs) and stores them in `localStorage`.  Subsequent API requests
send the access token as `Authorization: Bearer <token>`.

- **Access token** — JWT, valid for 30 minutes (configurable via `ACCESS_TOKEN_EXPIRE_MINUTES`).
- **Refresh token** — opaque 64-char hex string, stored in Redis, valid for 7 days
  (configurable via `REFRESH_TOKEN_EXPIRE_DAYS`).  Revoked on logout.

---

## Environment variable reference

Copy `.env.example` to `.env` and fill in all required values.

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | *(none)* | **Required.** 32-byte hex string.  Signs JWTs and derives the Fernet encryption key.  Generate with `python3 -c "import secrets; print(secrets.token_hex(32))"`. |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@db:5432/musicanalyser` | Async PostgreSQL DSN. |
| `REDIS_URL` | `redis://redis:6379/0` | Redis DSN used for Celery broker and token revocation list. |
| `BACKEND_CORS_ORIGINS` | `http://localhost:3000` | Comma-separated list of allowed CORS origins. Must include the public frontend URL in production. |
| `AUTH_PROVIDER` | `oidc` | Authentication protocol: `oidc` or `saml`. |
| `OIDC_DISCOVERY_URL` | *(empty)* | OIDC discovery document URL (required when `AUTH_PROVIDER=oidc`). |
| `OIDC_CLIENT_ID` | *(empty)* | OIDC client ID. |
| `OIDC_CLIENT_SECRET` | *(empty)* | OIDC client secret. |
| `OIDC_REDIRECT_URI` | *(empty, auto-detect)* | **Required in production.** Redirect URI registered with the IdP.  Must be `<public-app>/api/auth/oidc/callback`. |
| `OIDC_ROLES_CLAIM` | `roles` | Claim name in the OIDC userinfo that carries the roles list. |
| `SAML_IDP_METADATA_URL` | *(empty)* | URL to the IdP SAML metadata XML (required when `AUTH_PROVIDER=saml`). |
| `SAML_SP_ENTITY_ID` | *(empty)* | SAML service provider entity ID / issuer. |
| `SAML_SP_ACS_URL` | *(empty)* | SAML Assertion Consumer Service URL.  Must be `<public-app>/api/auth/saml/acs`. |
| `SAML_ROLES_ATTRIBUTE` | `roles` | SAML assertion attribute name carrying the roles list. |
| `FRONTEND_URL` | `http://localhost:3000` | **Required in production.** Public frontend URL used to build post-auth redirects. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | JWT access token lifetime in minutes. |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token lifetime in days. |
| `SPOTIFY_CLIENT_ID` | *(empty)* | Spotify app client ID. |
| `SPOTIFY_CLIENT_SECRET` | *(empty)* | Spotify app client secret. |
| `SPOTIFY_REDIRECT_URI` | `http://localhost:8000/api/spotify/callback` | Spotify OAuth callback URI. |
| `SMTP_HOST` | `localhost` | SMTP server hostname. |
| `SMTP_PORT` | `587` | SMTP server port. |
| `SMTP_USERNAME` | *(empty)* | SMTP username. |
| `SMTP_PASSWORD` | *(empty)* | SMTP password. |
| `SMTP_FROM` | `noreply@example.com` | Sender email address. |
| `SMTP_TLS` | `true` | Enable STARTTLS. |

---

## Documentation

| Document | Description |
|---|---|
| [Requirements](docs/requirements.md) | Original problem statement (preserved for reference) |
| [Architecture](docs/architecture.md) | Tech-stack decisions, component overview, data model |
| [IdP Configuration](docs/idp-configuration.md) | Setting up OIDC and SAML providers, flow diagrams, troubleshooting |
| [API Reference](docs/api.md) | Endpoint summary |
| [Deployment](docs/deployment.md) | Production deployment, environment variables, backups |

### Sessions

| Session | Status | Description |
|---|---|---|
| [Session 01 — Foundation](docs/sessions/session-01-foundation.md) | ✅ Complete | Project skeleton, Docker, CI |
| [Session 02 — Auth](docs/sessions/session-02-auth.md) | ✅ Complete | SAML / OIDC authentication |
| [Session 03 — Spotify](docs/sessions/session-03-spotify.md) | ✅ Complete | Spotify OAuth & history |
| [Session 04 — AI](docs/sessions/session-04-ai.md) | ✅ Complete | AI provider adapters & analysis |
| [Session 05 — Scheduling](docs/sessions/session-05-scheduling.md) | ✅ Complete | Celery jobs & email |
| [Session 06 — Frontend Polish](docs/sessions/session-06-frontend.md) | ✅ Complete | Full UI/UX |
| [Session 07 — Deployment](docs/sessions/session-07-deployment.md) | ✅ Complete | Hardening & deploy pipeline |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic |
| Task queue | Celery 5 · Redis 7 |
| Database | PostgreSQL 16 |
| Frontend | React 18 · TypeScript · Vite · Tailwind CSS |
| Auth | OIDC (Authlib) / SAML 2.0 (python3-saml) |
| Containers | Docker · Docker Compose |
| CI/CD | GitHub Actions → GHCR |

---

## Project Structure

```
music-history-analyser/
├── backend/                 # Python FastAPI application
│   ├── app/
│   │   ├── main.py          # Application factory
│   │   ├── config.py        # Settings (env vars via Pydantic Settings)
│   │   ├── database.py      # Async SQLAlchemy engine
│   │   ├── dependencies.py  # FastAPI dependency helpers (auth, role enforcement)
│   │   ├── middleware.py     # Security headers middleware
│   │   ├── models/          # ORM models
│   │   ├── routers/         # FastAPI routers
│   │   │   └── auth.py      # OIDC & SAML login, logout, /me
│   │   ├── schemas/         # Pydantic schemas
│   │   ├── services/        # Business logic
│   │   │   ├── auth_service.py  # JWT, token lifecycle, user upsert, IdP helpers
│   │   │   ├── ai/          # AI provider adapters (AIProvider ABC)
│   │   │   └── music/       # Music provider adapters (MusicProvider ABC)
│   │   └── tasks/           # Celery tasks
│   ├── alembic/             # DB migrations
│   └── tests/               # pytest tests
├── frontend/                # React + TypeScript SPA
│   └── src/
│       ├── pages/
│       │   ├── LoginPage.tsx        # Sign-in button
│       │   └── AuthCallbackPage.tsx # Token extraction after IdP redirect
│       ├── components/      # Reusable UI components
│       ├── services/
│       │   └── authApi.ts   # Auth API client (fetchMe, logout, getLoginUrl)
│       ├── hooks/
│       │   └── useAuth.ts   # AuthProvider context + useAuth hook
│       └── types/           # TypeScript types
├── docs/                    # Architecture, API, auth & session docs
├── docker-compose.yml       # Local development stack
├── docker-compose.prod.yml  # Production stack
└── .env.example             # Environment variable template
```

---

## Contributing

1. Pick a session doc from `docs/sessions/` as your work scope.
2. Create a branch named `feature/<session-name>`.
3. Implement the session and open a PR.
4. CI must be green before merging.
