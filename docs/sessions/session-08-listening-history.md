# Session 08 — Listening History Shadow Database & Top-Track Analysis

## Status: ✅ Completed

## Goal

Build a persistent, provider-agnostic shadow database that stores a user's
streaming history, automatically kept up-to-date via configurable polling.
Simultaneously, replace the ad-hoc "recently played" call in the AI analysis
with the richer `/v1/me/top/artists` and `/v1/me/top/tracks` Spotify endpoints.

## Prerequisite
Session 07 completed and merged.

## Scope

### 1. Generic Listening-History Data Model
New tables added via Alembic migration `20260326005`:

| Table          | Primary Key                          | Purpose                                              |
|----------------|--------------------------------------|------------------------------------------------------|
| `artists`      | `(provider, external_id)`            | Artist/creator; keyed by service ID                  |
| `albums`       | `(provider, external_id)`            | Release (album, EP, single)                          |
| `tracks`       | `(provider, external_id)`            | Playable item; `media_type` column supports videos   |
| `track_artists`| `(track_provider, track_external_id, artist_provider, artist_external_id)` | M2M junction |
| `play_events`  | UUID                                 | One row per (account, track, played_at) triple       |

The `(provider, external_id)` composite key is the Spotify ID today and will
support additional providers (YouTube, Apple Music, …) without schema changes.

The `tracks.media_type` column (`"track"` | `"video"` | …) makes the schema
forward-compatible for YouTube/video content.

A `UNIQUE` constraint on `(streaming_account_id, track_provider, track_external_id, played_at)`
in `play_events` prevents duplicate imports.

### 2. Polling Configuration on `spotify_accounts`
Three new columns added to the existing `spotify_accounts` table:
- `poll_interval_minutes` INTEGER NOT NULL DEFAULT 60 — per-account interval (1–1440 min)
- `polling_enabled`       BOOLEAN NOT NULL DEFAULT TRUE — pause/resume polling without deleting
- `last_polled_at`        DATETIME NULL — used as the Spotify `after` cursor

### 3. History Service (`app/services/history_service.py`)
- `poll_account(db, account_id)` — refreshes token if needed, fetches recently-played,
  upserts artists/albums/tracks, inserts new `PlayEvent` rows, advances the cursor.
- `get_accounts_due_for_poll(db)` — returns accounts whose next poll is due now.

### 4. Celery Polling Tasks (`app/tasks/history_tasks.py`)
- `poll_history_for_account` — per-account Celery task (max 3 retries).
- `check_due_history_polls` — beat task running every minute; dispatches per-account tasks.

### 5. Top Tracks & Top Artists for AI Analysis
`MusicProvider` base extended with two new abstract methods:
- `get_top_tracks(access_token, *, limit, time_range)`
- `get_top_artists(access_token, *, limit, time_range)`

`SpotifyAdapter` implements both, calling:
- `GET /v1/me/top/tracks?time_range=...&limit=...`
- `GET /v1/me/top/artists?time_range=...&limit=...`

`SPOTIFY_SCOPES` updated to include `user-top-read`.

`analysis_service.run_analysis()` now fetches top tracks **and** top artists
(neither is persisted in the DB — they are ephemeral per-run inputs to the AI).
The `time_window_days` parameter is mapped to a Spotify `time_range`:
- ≤ 28 days → `short_term`
- ≤ 180 days → `medium_term`
- > 180 days → `long_term`

### 6. New & Updated API Endpoints

| Method | Path                                          | Description                                    |
|--------|-----------------------------------------------|------------------------------------------------|
| PATCH  | `/api/spotify/accounts/{id}`                  | Update `poll_interval_minutes` / `polling_enabled` |
| POST   | `/api/spotify/accounts/{id}/poll`             | Manually trigger a history poll (async, 202)   |
| GET    | `/api/spotify/accounts/{id}/play-events`      | List stored play events from the shadow DB; supports `limit` / `offset` |

The existing `GET /api/spotify/accounts/{id}/history` endpoint is retained
for backward compatibility (live Spotify pull).

## Acceptance Criteria

- [x] `artists`, `albums`, `tracks`, `track_artists`, `play_events` tables created via migration
- [x] `spotify_accounts` extended with `poll_interval_minutes`, `polling_enabled`, `last_polled_at`
- [x] `history_service.poll_account` upserts entities and stores play events
- [x] Duplicate play events are ignored (unique constraint + pre-check)
- [x] `last_polled_at` cursor advances only forward
- [x] Polling skipped immediately when `polling_enabled = False`
- [x] Celery beat task `check_due_history_polls` dispatches per-account tasks every minute
- [x] `MusicProvider` ABC declares `get_top_tracks` / `get_top_artists`
- [x] `SpotifyAdapter` implements both (calls Spotify top-tracks/artists endpoints)
- [x] AI analysis uses top tracks + top artists (not recently-played)
- [x] `PATCH /api/spotify/accounts/{id}` enforces 1–1440 interval range, returns 403 for non-owners
- [x] `POST /api/spotify/accounts/{id}/poll` dispatches Celery task, returns 202
- [x] `GET /api/spotify/accounts/{id}/play-events` returns 403 for non-owners
- [x] All new behaviour covered by tests (17 new tests, 120 total passing)

## Out of Scope (Deferred)
- Frontend UI for poll configuration and play-event list (configurable toggle + interval input)
- Data management / admin UI (see *Ideas* section below)
- Apple Music / YouTube provider adapters
- Retroactive history import beyond the Spotify 50-track window

## Key Files Created / Modified

```
backend/
  app/models/listening_history.py        ← NEW: Artist, Album, Track, TrackArtist, PlayEvent
  app/models/spotify_account.py          ← + poll_interval_minutes, polling_enabled, last_polled_at
  app/models/__init__.py                 ← + new model exports
  app/services/music/base.py             ← + Artist, Album, TopArtist, TopTrack DTOs + abstract methods
  app/services/music/spotify.py          ← + get_top_tracks, get_top_artists; enriched get_recently_played
  app/services/history_service.py        ← NEW: poll_account, get_accounts_due_for_poll
  app/services/analysis_service.py       ← use top tracks/artists for AI prompt
  app/tasks/history_tasks.py             ← NEW: poll_history_for_account, check_due_history_polls
  app/tasks/celery_app.py                ← + history_tasks module + beat schedule entry
  app/routers/spotify.py                 ← + PATCH /accounts/{id}, POST /accounts/{id}/poll,
                                            GET /accounts/{id}/play-events
  app/schemas/spotify.py                 ← + SpotifyAccountPollUpdate, PlayEventRead;
                                            SpotifyAccountRead extended
  tests/test_listening_history.py        ← NEW: 17 tests

alembic/versions/20260326_005_add_listening_history.py   ← NEW migration
```

---

## Ideas: Data Management UI (Not Yet Implemented)

The following ideas should be built in a future session.  They address how
operators and users can manage accumulated listening-history data.

### A. User Self-Service Page: "My Data"
A dedicated settings page (`/settings/my-data`) where each user can:

1. **View stats** — total play events stored, date range of history, number of
   unique tracks/artists across all linked accounts.
2. **Delete history for a specific account** — a "Clear listening history"
   button that hard-deletes all `PlayEvent` rows for the selected
   `streaming_account_id`.  Orphaned `tracks`/`artists`/`albums` that are no
   longer referenced by any `play_event` can be cleaned up in a background job.
3. **Delete all personal data** — a two-step confirmation dialog that:
   - Deletes all `PlayEvent` rows for all of the user's accounts
   - Deletes all `SpotifyAccount` rows (cascades to play events)
   - Deletes the `User` row (cascades to analyses, schedules, etc.)
   - Triggers a background orphan-cleanup job
4. **Export history (GDPR)** — "Download my data" button generating a JSON
   or CSV export of all `PlayEvent` rows enriched with track metadata.

### B. Admin Panel: Data Hygiene
A new admin section (extending the existing `/admin` endpoints):

1. **User data wipe** — admin can hard-delete a specific user and trigger
   orphan cleanup (useful after a GDPR "right to erasure" request).
2. **Orphan cleanup job** — a manual or scheduled task that:
   - Finds `Track` rows not referenced by any `PlayEvent`
   - Finds `Artist` rows not linked to any surviving `Track` via `TrackArtist`
   - Finds `Album` rows not referenced by any surviving `Track`
   - Deletes them in dependency order (`track_artists` → `tracks` → `albums`
     and `artists`) to keep the catalogue clean.
   - Reports counts of deleted rows in the admin UI.
3. **Storage dashboard** — table showing row counts for
   `play_events` / `tracks` / `artists` / `albums` and per-user history size.

### C. Automatic Orphan Cleanup via Celery
A low-priority Celery task (`cleanup_orphaned_catalogue`) that runs nightly
(e.g. `crontab(hour=3, minute=0)`).  It wraps the orphan-cleanup logic in a
transaction and logs counts so operators can monitor catalogue growth.

### D. Retention Policy
An optional configurable retention window (e.g. `HISTORY_RETENTION_DAYS=365`).
`PlayEvent` rows older than the window are deleted by the nightly cleanup task.
Users can also set a per-account retention window via the "My Data" page.

### E. API Endpoints to Support the Above

| Method | Path                                              | Description                                         |
|--------|---------------------------------------------------|-----------------------------------------------------|
| DELETE | `/api/spotify/accounts/{id}/play-events`          | Clear all history for one account (user-level)      |
| DELETE | `/api/users/me/data`                              | Delete all user data + trigger orphan cleanup       |
| GET    | `/api/users/me/data/export`                       | Stream a JSON/CSV export of the user's history      |
| POST   | `/api/admin/cleanup/orphans`                      | Trigger orphan-catalogue cleanup (admin only)       |
| GET    | `/api/admin/stats/storage`                        | Row-count dashboard per entity (admin only)         |
