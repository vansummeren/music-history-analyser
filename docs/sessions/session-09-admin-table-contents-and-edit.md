# Session 09 — Admin Table Contents & Edit

## Goal

Two features were added on top of the existing admin panel:

1. **Table contents** — admins can select a user and see what they listened to,
   when their last schedules ran, how many Spotify accounts they have linked, etc.
2. **Edit** — analyses and AI configurations can now be updated in-place (name,
   prompt, display name, API key rotation).

---

## Feature 1: Admin User List & Detail

### Backend

#### New schemas (`backend/app/schemas/admin.py`)

| Schema | Fields |
|--------|--------|
| `AdminUserSummary` | id, display_name, email, role, created_at, spotify_accounts_count, analyses_count, schedules_count, play_events_count |
| `AdminSpotifyAccountSummary` | id, spotify_user_id, display_name, polling_enabled, last_polled_at, play_events_count |
| `AdminAnalysisSummary` | id, name, prompt, run_count, last_run_at, last_run_status |
| `AdminScheduleSummary` | id, analysis_id, analysis_name, cron, time_window_days, recipient_email, is_active, last_run_at, next_run_at |
| `AdminUserDetail` | id, display_name, email, role, created_at, spotify_accounts, analyses, schedules |

#### New endpoints (`backend/app/routers/admin.py`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/admin/users` | admin | List all users with summary counts |
| `GET` | `/api/admin/users/{user_id}` | admin | Full detail for a single user |

Both endpoints require the `admin` role (403 otherwise, 401 if unauthenticated).

### Frontend

`AdminPanelPage` was extended with a second section — **Users** — that renders a
clickable table of all users.  Clicking a row fetches the user's detail and
switches to a `UserDetailPanel` component that displays:

- User identity (name, email, role, join date)
- **Spotify Accounts** table — display name, play-events count, last-polled
  timestamp, polling enabled/disabled
- **Analyses** list — name, prompt (truncated), run count, last-run timestamp,
  and a colour-coded status badge
- **Schedules** table — linked analysis name, cron expression, last-ran
  timestamp, active flag

A "Back to user list" button returns to the summary view.

New API helpers in `adminApi.ts`:

```ts
getAdminUsers(): Promise<AdminUserSummary[]>
getAdminUserDetail(userId: string): Promise<AdminUserDetail>
```

---

## Feature 2: Inline Edit

### Analyses

A pencil icon was added to each analysis card in `AnalysisPage`.  Clicking it
switches the card into edit mode where the **Name** and **Prompt** fields can be
changed.  Saving calls `PATCH /api/analyses/{id}`; cancelling restores the
original values.

#### Backend

New schema `AnalysisUpdate` (`backend/app/schemas/analysis.py`):

```python
class AnalysisUpdate(BaseModel):
    name: str | None = None
    prompt: str | None = None
```

New endpoint in `backend/app/routers/analyses.py`:

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `PATCH` | `/api/analyses/{analysis_id}` | owner | Update name and/or prompt |

Returns 404 if the analysis does not exist, 403 if it belongs to another user.

#### Frontend (`analysisApi.ts`)

```ts
export interface AnalysisUpdate { name?: string; prompt?: string }
updateAnalysis(id: string, data: AnalysisUpdate): Promise<Analysis>
```

### AI Configurations

A pencil icon was added to each AI config card in `AIConfigPage`.  Clicking it
shows editable fields for **Display Name** and an optional **New API Key** (the
current key is never shown; leaving the field blank keeps the existing key).

#### Backend

New schema `AIConfigUpdate` (`backend/app/schemas/ai.py`):

```python
class AIConfigUpdate(BaseModel):
    display_name: str | None = None
    api_key: str | None = None
```

New endpoint in `backend/app/routers/ai_configs.py`:

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `PATCH` | `/api/ai-configs/{config_id}` | owner | Update display name and/or API key |

When `api_key` is provided it is encrypted with Fernet before storage (same
as during creation).  Returns 404/403 on the usual conditions.

#### Frontend (`aiApi.ts`)

```ts
export interface AIConfigUpdate { display_name?: string; api_key?: string }
updateAIConfig(id: string, data: AIConfigUpdate): Promise<AIConfig>
```

---

## Tests

| File | New tests |
|------|-----------|
| `backend/tests/test_analysis.py` | 4 — PATCH happy path, partial update, 403, 404 |
| `backend/tests/test_ai.py` | 4 — display-name update, API-key rotation, 403, 404 |
| `backend/tests/test_admin.py` | 6 — list users (auth/role/data), get detail (role/404/data) |

Total: **153 backend** tests passing, **50 frontend** tests passing.

---

## Version

Bumped `1.0.3` → **`1.0.4`** in:

- `frontend/package.json`
- `backend/app/config.py`
- `backend/Dockerfile`
