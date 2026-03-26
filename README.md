# Music History Analyser

[![CI](https://github.com/vansummeren/music-history-analyser/actions/workflows/ci.yml/badge.svg)](https://github.com/vansummeren/music-history-analyser/actions/workflows/ci.yml)
[![Deploy](https://github.com/vansummeren/music-history-analyser/actions/workflows/deploy.yml/badge.svg)](https://github.com/vansummeren/music-history-analyser/actions/workflows/deploy.yml)

Analyse your Spotify listening history with AI. Connect your Spotify account, choose an AI
provider (Claude, Perplexity, …), write a custom prompt, and schedule recurring analyses that
land in your inbox.

---

## Quick Start (local development)

```bash
# Clone
git clone https://github.com/vansummeren/music-history-analyser.git
cd music-history-analyser

# Configure environment
cp .env.example .env
# Edit .env — fill in SECRET_KEY, OIDC / SAML credentials, Spotify keys, SMTP settings

# Start all services
docker compose up --build

# In a separate terminal, run DB migrations
docker compose exec backend alembic upgrade head
```

- **Frontend**: http://localhost:3000  
- **API (interactive docs)**: http://localhost:8000/docs

---

## Documentation

| Document | Description |
|---|---|
| [Requirements](docs/requirements.md) | Original problem statement (preserved for reference) |
| [Architecture](docs/architecture.md) | Tech-stack decisions, component overview, data model |
| [API Reference](docs/api.md) | Endpoint summary |
| [Deployment](docs/deployment.md) | Production deployment, env vars, backups |

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
│   │   ├── config.py        # Settings (env vars)
│   │   ├── database.py      # Async SQLAlchemy engine
│   │   ├── models/          # ORM models
│   │   ├── routers/         # FastAPI routers
│   │   ├── schemas/         # Pydantic schemas
│   │   ├── services/        # Business logic
│   │   │   ├── ai/          # AI provider adapters (AIProvider ABC)
│   │   │   └── music/       # Music provider adapters (MusicProvider ABC)
│   │   └── tasks/           # Celery tasks
│   ├── alembic/             # DB migrations
│   └── tests/               # pytest tests
├── frontend/                # React + TypeScript SPA
│   └── src/
│       ├── pages/           # Route-level pages
│       ├── components/      # Reusable UI components
│       ├── services/        # API client wrappers
│       ├── hooks/           # Custom React hooks
│       └── types/           # TypeScript types
├── docs/                    # Architecture & session docs
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
