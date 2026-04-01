# Copilot Instructions — Music History Analyser

## Linting & Type-Checking (Backend)

**Always run these checks before committing backend changes:**

```bash
cd backend
# Linter — must pass with zero errors
ruff check .

# Type checker — must pass with zero errors
# Requires: pip install -r requirements.txt -r requirements-dev.txt
mypy app
```

- When adding a **new Python dependency**, also add it to `backend/requirements.txt`.
- If the new dependency does **not** ship inline types (py.typed), add the
  corresponding `types-*` stub package to `backend/requirements-dev.txt`
  so that `mypy` stays green.  
  Example: `markdown` → `types-Markdown` in requirements-dev.txt.

## Linting (Frontend)

```bash
cd frontend
npm ci
npm run lint   # ESLint
```

## Tests

```bash
# Backend (from backend/)
pip install -r requirements.txt -r requirements-dev.txt
pytest --cov=app

# Frontend (from frontend/)
npm ci
npm test       # Vitest
```

## CI Pipeline

The CI workflow (`.github/workflows/ci.yml`) runs on every push and PR:

| Job | What it checks |
|---|---|
| **Backend — Lint** | `ruff check .` + `mypy app` |
| **Backend — Test** | `pytest --cov=app` |
| **Frontend — Lint** | `npm run lint` |
| **Frontend — Test** | `npm test` |
| **Docker — Build** | Smoke-builds both Docker images |
| **pip-audit** | Scans Python deps for known vulnerabilities |
| **npm audit** | Scans JS deps for known vulnerabilities |

All lint and test jobs **must pass** before merging.
