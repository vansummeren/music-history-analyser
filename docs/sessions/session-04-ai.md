# Session 04 — AI Provider Integration & Analysis Configuration

## Goal
Allow authenticated users to add their AI API keys, create named analysis configurations
(which AI provider + which Spotify account + custom prompt), and trigger a manual one-shot
analysis run.

## Prerequisite
Session 03 completed and merged.

## Scope
- Abstract `AIProvider` base class (`backend/app/services/ai/base.py`)
- Claude adapter (`anthropic` SDK)
- Perplexity adapter (OpenAI-compatible REST)
- `AIConfig` model + `Analysis` model + `AnalysisRun` model + Alembic migrations
- Encrypted API key storage (reuse `crypto.py` from session 03)
- API endpoints:
  - `POST   /api/ai-configs` — add AI config (provider + encrypted key + display name)
  - `GET    /api/ai-configs` — list user's AI configs
  - `DELETE /api/ai-configs/{id}` — remove AI config
  - `POST   /api/analyses` — create analysis (link spotify_account + ai_config + prompt)
  - `GET    /api/analyses` — list analyses
  - `DELETE /api/analyses/{id}` — delete analysis
  - `POST   /api/analyses/{id}/run` — trigger immediate run (async, returns run id)
  - `GET    /api/analyses/{id}/runs` — list past runs
  - `GET    /api/analyses/{id}/runs/{run_id}` — get run result
- The analysis service: fetch history → build prompt → call AI → store result
- Frontend: AI config management page + Analysis configuration page + run result viewer

## Acceptance Criteria
- User can add Claude and Perplexity configs (API key stored encrypted)
- User can create an analysis linking a Spotify account and AI config
- Triggering a run fetches history, calls AI (mocked in tests), stores result
- Result text is returned via the run endpoint
- A user cannot see another user's configs or analyses (403)
- All service logic covered by unit tests with mocked external calls

## Out of Scope
- Scheduling (done in session 05)
- Email delivery (done in session 05)

## Key Files to Create / Modify

```
backend/
  app/models/ai_config.py
  app/models/analysis.py
  app/schemas/ai.py
  app/schemas/analysis.py
  app/routers/ai_configs.py
  app/routers/analyses.py
  app/services/ai/__init__.py   # AIProvider ABC
  app/services/ai/claude.py
  app/services/ai/perplexity.py
  app/services/analysis_service.py
  tests/test_ai.py
  tests/test_analysis.py

alembic/versions/<timestamp>_add_ai_and_analysis.py

frontend/
  src/pages/AIConfigPage.tsx
  src/pages/AnalysisPage.tsx
  src/components/RunResultViewer.tsx
  src/services/aiApi.ts
  src/services/analysisApi.ts
```
