# Session 01 — Foundation & Project Setup

## Status

> ✅ **Completed** — All acceptance criteria have been verified. The full project skeleton is in place, all linters pass (ruff, mypy, eslint), all tests pass (pytest, vitest), and the CI pipeline runs green.

## Goal
Establish the complete project skeleton so every subsequent session has a working base
to build on. By the end of this session all containers start, the database is reachable,
and the CI pipeline is green.

## Scope
- Python FastAPI project with proper package layout
- PostgreSQL connection via async SQLAlchemy 2
- Alembic migration setup (initial empty migration)
- Redis + Celery skeleton (worker boots, no tasks yet)
- React + TypeScript + Vite + Tailwind CSS frontend skeleton
- `docker-compose.yml` (all four services)
- `.env.example` with all required variables documented
- GitHub Actions CI workflow: lint → test → build
- Root `README.md` with quick-start instructions

## Acceptance Criteria
- `docker compose up` starts all services without errors
- `GET /api/health` returns `{"status": "ok"}`
- `pytest` passes (no tests yet → 0 collected, exit 0)
- `vitest` passes (no tests yet → 0 collected)
- CI workflow completes green on a push

## Out of Scope
- Any authentication
- Any Spotify integration
- Any AI integration

## Key Files to Create

```
backend/
  app/main.py            # FastAPI app factory + /api/health
  app/config.py          # Pydantic Settings
  app/database.py        # async engine + session dependency
  app/models/__init__.py
  app/routers/__init__.py
  app/services/__init__.py
  app/schemas/__init__.py
  app/tasks/celery_app.py
  tests/test_health.py
  Dockerfile
  requirements.txt
  alembic.ini
  alembic/env.py
  alembic/versions/.gitkeep

frontend/
  package.json
  vite.config.ts
  tailwind.config.ts
  tsconfig.json
  index.html
  src/main.tsx
  src/App.tsx
  src/pages/HomePage.tsx
  Dockerfile

docker-compose.yml
.env.example
.github/workflows/ci.yml
README.md  (updated)
```
