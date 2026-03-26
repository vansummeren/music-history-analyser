# Architecture

## Overview

**Music History Analyser** is a web application that lets authenticated users connect their Spotify
account, configure AI-powered analysis of their listening history, schedule recurring analysis jobs,
and receive results by e-mail.

```
┌─────────────────────────────────────────────────────┐
│                  Browser (SPA)                       │
│          React + TypeScript + Tailwind CSS           │
└────────────────────────┬────────────────────────────┘
                         │ HTTPS (REST / JSON)
         ┌───────────────▼──────────────────┐
         │        Backend Container         │
         │    Python 3.12 · FastAPI         │
         │  ┌──────────────────────────┐   │
         │  │  Auth (SAML/OIDC)        │   │
         │  │  Spotify OAuth           │   │
         │  │  AI provider adapters    │   │
         │  │  Analysis orchestration  │   │
         │  │  REST API                │   │
         │  └──────────────────────────┘   │
         │  ┌──────────────────────────┐   │
         │  │  Celery Worker           │   │
         │  │  (scheduled jobs)        │   │
         │  └──────────────────────────┘   │
         └──────┬────────────┬─────────────┘
                │            │
     ┌──────────▼──┐   ┌─────▼─────┐
     │  PostgreSQL  │   │   Redis   │
     │  Container   │   │ Container │
     │  (state/cfg) │   │ (queue)   │
     └─────────────┘   └───────────┘
```

Ingress is handled externally (e.g. Cloudflare Tunnel, nginx reverse proxy). The backend container
exposes only a single HTTP port; TLS termination lives outside the stack.

---

## Tech-Stack Decisions

| Concern | Choice | Rationale |
|---|---|---|
| **Backend language** | Python 3.12 | Widely adopted, excellent ecosystem for async APIs and data processing |
| **Backend framework** | FastAPI | Modern, async-first, auto-generated OpenAPI docs, strong typing via Pydantic |
| **ORM / migrations** | SQLAlchemy 2 + Alembic | Industry standard, async support, straightforward migrations |
| **Database** | PostgreSQL 16 | Robust, well-known, ideal for relational config & history data |
| **Task queue** | Celery 5 + Redis | Mature, well-documented scheduling and async job processing |
| **Auth** | `python3-saml` / Authlib (OIDC) | Supports both SAML 2.0 and OIDC without exotic dependencies |
| **Frontend language** | TypeScript | Type safety reduces bugs |
| **Frontend framework** | React 18 | Industry standard SPA framework |
| **Frontend styling** | Tailwind CSS + shadcn/ui | Modern, clean design system; utility-first avoids CSS bloat |
| **Frontend build** | Vite | Fast, zero-config |
| **Containerisation** | Docker + Docker Compose | Simple multi-container orchestration |
| **CI/CD** | GitHub Actions | Native to the repo, free for public repos |
| **Email** | SMTP (via `aiosmtplib`) | Universal, no third-party dependency |
| **Secret management** | Environment variables + `.env` | Simple, container-friendly, no extra service needed at this scale |

### Expandability

* **Music providers**: a `MusicProvider` abstract base class in `backend/app/services/music/`
  makes it trivial to add Tidal, Apple Music, etc.
* **AI providers**: an `AIProvider` abstract base class in `backend/app/services/ai/`
  makes it trivial to add OpenAI, Gemini, Mistral, etc.
* **Auth backends**: Authlib supports multiple OIDC providers; the SAML config is file-driven.

---

## Component Responsibilities

### Backend (`backend/`)

| Module | Responsibility |
|---|---|
| `app/main.py` | FastAPI application factory, middleware, router registration |
| `app/config.py` | Pydantic-based settings loaded from environment variables |
| `app/database.py` | Async SQLAlchemy engine & session factory |
| `app/models/` | SQLAlchemy ORM models |
| `app/schemas/` | Pydantic request/response schemas (validation & serialisation) |
| `app/routers/` | FastAPI routers (one per feature domain) |
| `app/services/` | Business logic, completely decoupled from HTTP |
| `app/services/ai/` | AI provider adapters behind a common interface |
| `app/services/music/` | Music provider adapters behind a common interface |
| `app/tasks/` | Celery task definitions |
| `alembic/` | Database migration scripts |
| `tests/` | pytest unit and integration tests |

### Frontend (`frontend/`)

| Module | Responsibility |
|---|---|
| `src/pages/` | Route-level page components |
| `src/components/` | Reusable UI components |
| `src/services/` | API client wrappers (axios) |
| `src/hooks/` | Custom React hooks (auth state, data fetching) |
| `src/types/` | Shared TypeScript type definitions |

---

## Data Model (high level)

```
users
  id · email · display_name · created_at · last_login_at

spotify_accounts
  id · user_id (FK) · spotify_user_id · display_name
  access_token (encrypted) · refresh_token (encrypted) · token_expires_at · linked_at

ai_configs
  id · user_id (FK) · provider · api_key (encrypted) · display_name · created_at

analyses
  id · user_id (FK) · spotify_account_id (FK) · ai_config_id (FK)
  prompt · display_name · created_at

schedules
  id · analysis_id (FK) · cron_expression · time_window · recipient_email
  is_active · last_run_at · next_run_at · created_at

analysis_runs
  id · schedule_id (FK, nullable) · analysis_id (FK)
  status (pending/running/completed/failed)
  result_text · error_message · started_at · finished_at
```

Sensitive values (tokens, API keys) are encrypted at rest using `cryptography.fernet`
with a key derived from `SECRET_KEY` in the environment.

---

## Security Considerations

* No unauthenticated access to any API endpoint except the SAML/OIDC callback.
* All inter-container traffic stays on an isolated Docker network.
* Secrets (tokens, API keys) are encrypted in the database.
* Input validation is performed via Pydantic on every request.
* SQL injection is prevented by using SQLAlchemy ORM (parameterised queries only).
* CORS is restricted to the configured frontend origin.
* Rate limiting is applied to the auth and Spotify-link endpoints.
* Dependency updates are automated by Dependabot.

---

## Container Layout

| Service | Image | Ports (internal) | Notes |
|---|---|---|---|
| `backend` | custom build | `8000` | FastAPI + Celery worker in one image, separate entrypoints |
| `worker` | same image as backend | — | Celery worker; runs `celery -A app.tasks worker` |
| `db` | `postgres:16-alpine` | `5432` | Data volume mounted |
| `redis` | `redis:7-alpine` | `6379` | Used as Celery broker and result backend |

> **Why backend + worker share an image?**
> They share 100 % of the application code. A single image avoids drift and keeps the
> Docker layer cache efficient. They are separated at the `command` level only.

---

## CI / CD Pipeline

```
┌──────────────────────────────────────────────────────┐
│  On every push / PR                                   │
│  1. Lint  (ruff, mypy, eslint)                        │
│  2. Unit + integration tests (pytest, vitest)         │
│  3. Build Docker image (backend + frontend)           │
└──────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│  On push to `main`                                    │
│  4. Push images to GitHub Container Registry (ghcr)   │
│  5. (Optional) trigger deploy webhook on Docker host  │
└──────────────────────────────────────────────────────┘
```
