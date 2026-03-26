# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project uses calendar versioning (`YYYY.M.PATCH`).

---

## [2026.3.1] — 2026-03-26 (Pre-release)

### Added

#### Foundation (Session 01)
- Project skeleton with FastAPI backend, React + TypeScript + Vite + Tailwind CSS frontend
- Async SQLAlchemy 2 with PostgreSQL 16
- Alembic database migrations
- Celery 5 + Redis 7 task queue
- Docker Compose stack for local development and production
- GitHub Actions CI pipeline (ruff, mypy, pytest, eslint, vitest)

#### Authentication (Session 02)
- OIDC authentication via Authlib
- SAML 2.0 authentication via python3-saml
- JWT-based session management

#### Spotify Integration (Session 03)
- Spotify OAuth 2.0 connection flow
- Spotify listening history retrieval
- Fernet encryption for stored OAuth tokens (`crypto.py`)
- `SpotifyAccount` model and 5 REST endpoints (`/spotify/*`)

#### AI Analysis (Session 04)
- Pluggable AI provider architecture (`AIProvider` ABC)
- Claude (Anthropic) adapter
- Perplexity adapter
- `AIConfig`, `Analysis`, and `AnalysisRun` models
- 9 REST endpoints for AI config and analysis management
- Alembic migration `20260326003`

#### Scheduling & Email (Session 05)
- `Schedule` model with cron-expression support
- Celery beat task `check_due_schedules` for recurring analysis execution
- Email delivery of analysis results via aiosmtplib
- `SchedulesPage`, `ScheduleCard`, and `CronEditor` frontend components
- Alembic migration `20260326004`

#### Frontend Polish (Session 06)
- `AppShell`, `Sidebar`, `Header` layout components
- `StatCard`, `Toast`, `LoadingSkeleton`, `EmptyState` UI components
- `DashboardPage` and `RunResultPage` route pages
- `useAuth` and `useToast` React context hooks
- Application rebranded as **Amadeus**

#### Production Hardening & Deployment (Session 07)
- `SecurityHeadersMiddleware` (CSP, HSTS, X-Frame-Options, …)
- Per-user rate limiting service (`rate_limit.py`)
- Non-root nginx Dockerfile for the frontend container
- `pip-audit` and `npm audit` security scanning in CI
- `workflow_run`-triggered deploy workflow pushing images to GHCR
- 74 pytest tests · 48 vitest tests

### Changed
- Nothing (first release)

### Fixed
- Nothing (first release)

---

[2026.3.1]: https://github.com/vansummeren/music-history-analyser/releases/tag/2026.3.1
