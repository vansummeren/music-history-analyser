# Database Schema

Music History Analyser uses **PostgreSQL 16** as its relational database.
All schema changes are managed with **Alembic** (migrations live in `backend/alembic/versions/`).

Sensitive values (OAuth tokens, API keys) are **Fernet-encrypted** before being written to the
database.  See `backend/app/services/crypto.py` for the encryption helpers.

---

## Table overview

| Table | Description |
|---|---|
| [`users`](#users) | Authenticated users (SAML / OIDC) |
| [`spotify_accounts`](#spotify_accounts) | Linked Spotify accounts with encrypted tokens and polling config |
| [`ai_configs`](#ai_configs) | AI provider configurations with encrypted API keys |
| [`analyses`](#analyses) | Named analysis definitions (prompt + provider pair) |
| [`analysis_runs`](#analysis_runs) | Individual execution results for an analysis |
| [`schedules`](#schedules) | Recurring cron-based schedule for an analysis |
| [`artists`](#artists) | Music artists / content creators (provider-agnostic) |
| [`albums`](#albums) | Releases (albums, EPs, singles …) |
| [`tracks`](#tracks) | Playable media items (tracks or videos) |
| [`track_artists`](#track_artists) | Many-to-many junction between tracks and artists |
| [`play_events`](#play_events) | Individual play events for a streaming account |

---

## users

Stores every user who has logged in via SAML 2.0 or OIDC.

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid_generate_v4()` | **Primary key** |
| `sub` | `VARCHAR(255)` | NO | — | Unique subject claim from the IdP. **Unique** |
| `provider` | `VARCHAR(50)` | NO | — | Auth provider identifier (e.g. `"saml"`, `"oidc"`) |
| `email` | `VARCHAR(255)` | YES | `NULL` | Email address from the IdP (may be absent) |
| `display_name` | `VARCHAR(255)` | YES | `NULL` | Human-readable name from the IdP |
| `role` | `VARCHAR(20)` | NO | `'user'` | Role (`"user"` or `"admin"`) |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | Row creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | NO | `now()` | Last update timestamp |

**Keys & constraints**

| Type | Columns | Notes |
|---|---|---|
| Primary key | `id` | |
| Unique | `sub` | One row per IdP subject |

---

## spotify_accounts

One row per linked Spotify account.  Tokens are stored encrypted.

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid_generate_v4()` | **Primary key** |
| `user_id` | `UUID` | NO | — | **Foreign key** → `users.id` (CASCADE delete) |
| `spotify_user_id` | `VARCHAR(255)` | NO | — | Spotify's own user ID. **Unique** |
| `display_name` | `VARCHAR(255)` | YES | `NULL` | Display name from Spotify |
| `email` | `VARCHAR(255)` | YES | `NULL` | Email address from Spotify |
| `encrypted_access_token` | `TEXT` | NO | — | Fernet-encrypted OAuth access token |
| `encrypted_refresh_token` | `TEXT` | NO | — | Fernet-encrypted OAuth refresh token |
| `token_expires_at` | `TIMESTAMPTZ` | NO | — | When the access token expires |
| `scopes` | `TEXT` | NO | `''` | Space-separated OAuth scopes granted |
| `poll_interval_minutes` | `INTEGER` | NO | `60` | How often (minutes) to poll recently-played history |
| `polling_enabled` | `BOOLEAN` | NO | `true` | Whether automatic polling is active for this account |
| `last_polled_at` | `TIMESTAMPTZ` | YES | `NULL` | Timestamp of the last successful poll (used as API cursor) |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | Row creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | NO | `now()` | Last update timestamp |

**Keys & constraints**

| Type | Columns | Notes |
|---|---|---|
| Primary key | `id` | |
| Foreign key | `user_id` → `users.id` | ON DELETE CASCADE |
| Unique | `spotify_user_id` | One row per Spotify account |

---

## ai_configs

Stores AI provider configurations.  The API key is encrypted at rest.

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid_generate_v4()` | **Primary key** |
| `user_id` | `UUID` | NO | — | **Foreign key** → `users.id` (CASCADE delete) |
| `provider` | `VARCHAR(50)` | NO | — | AI provider slug (`"claude"` or `"perplexity"`) |
| `display_name` | `VARCHAR(255)` | NO | — | Human-readable label chosen by the user |
| `encrypted_api_key` | `TEXT` | NO | — | Fernet-encrypted API key |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | Row creation timestamp |

**Keys & constraints**

| Type | Columns | Notes |
|---|---|---|
| Primary key | `id` | |
| Foreign key | `user_id` → `users.id` | ON DELETE CASCADE |

---

## analyses

A named analysis definition: which Spotify account, which AI config, and what prompt to use.

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid_generate_v4()` | **Primary key** |
| `user_id` | `UUID` | NO | — | **Foreign key** → `users.id` (CASCADE delete) |
| `spotify_account_id` | `UUID` | NO | — | **Foreign key** → `spotify_accounts.id` (CASCADE delete) |
| `ai_config_id` | `UUID` | NO | — | **Foreign key** → `ai_configs.id` (CASCADE delete) |
| `name` | `VARCHAR(255)` | NO | — | Human-readable name for this analysis |
| `prompt` | `TEXT` | NO | — | The prompt template sent to the AI provider |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | Row creation timestamp |

**Keys & constraints**

| Type | Columns | Notes |
|---|---|---|
| Primary key | `id` | |
| Foreign key | `user_id` → `users.id` | ON DELETE CASCADE |
| Foreign key | `spotify_account_id` → `spotify_accounts.id` | ON DELETE CASCADE |
| Foreign key | `ai_config_id` → `ai_configs.id` | ON DELETE CASCADE |

---

## analysis_runs

One row per execution of an analysis.  Captures the AI model used, token counts, and the
result or error.

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid_generate_v4()` | **Primary key** |
| `analysis_id` | `UUID` | NO | — | **Foreign key** → `analyses.id` (CASCADE delete) |
| `status` | `VARCHAR(20)` | NO | `'pending'` | Run status: `pending`, `running`, `completed`, or `failed` |
| `result_text` | `TEXT` | YES | `NULL` | AI-generated result text |
| `model` | `VARCHAR(255)` | YES | `NULL` | Exact model identifier used (e.g. `"claude-3-5-sonnet-20241022"`) |
| `input_tokens` | `INTEGER` | YES | `NULL` | Number of input tokens consumed |
| `output_tokens` | `INTEGER` | YES | `NULL` | Number of output tokens consumed |
| `error` | `TEXT` | YES | `NULL` | Error message if the run failed |
| `started_at` | `TIMESTAMPTZ` | YES | `NULL` | When execution started |
| `completed_at` | `TIMESTAMPTZ` | YES | `NULL` | When execution finished (success or failure) |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | Row creation timestamp |

**Keys & constraints**

| Type | Columns | Notes |
|---|---|---|
| Primary key | `id` | |
| Foreign key | `analysis_id` → `analyses.id` | ON DELETE CASCADE |

---

## schedules

Recurring cron-based schedules that trigger analysis runs automatically.

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid_generate_v4()` | **Primary key** |
| `user_id` | `UUID` | NO | — | **Foreign key** → `users.id` (CASCADE delete) |
| `analysis_id` | `UUID` | NO | — | **Foreign key** → `analyses.id` (CASCADE delete) |
| `cron` | `VARCHAR(100)` | NO | — | Standard cron expression (e.g. `"0 8 * * 1"` for every Monday at 08:00 UTC) |
| `time_window_days` | `INTEGER` | NO | `7` | Number of days of Spotify history to include in the run |
| `recipient_email` | `VARCHAR(255)` | NO | — | Email address to send the result to |
| `is_active` | `BOOLEAN` | NO | `true` | Whether this schedule is currently active |
| `last_run_at` | `TIMESTAMPTZ` | YES | `NULL` | Timestamp of the last triggered run |
| `next_run_at` | `TIMESTAMPTZ` | NO | — | Pre-computed timestamp of the next scheduled run |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | Row creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | NO | `now()` | Last update timestamp |

**Keys & constraints**

| Type | Columns | Notes |
|---|---|---|
| Primary key | `id` | |
| Foreign key | `user_id` → `users.id` | ON DELETE CASCADE |
| Foreign key | `analysis_id` → `analyses.id` | ON DELETE CASCADE |

---

## artists

Provider-agnostic artist catalogue.  The composite primary key allows the same table to hold
artists from Spotify, YouTube, and any future provider without conflicts.

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| `provider` | `VARCHAR(50)` | NO | — | **PK (part 1)** — streaming provider slug (e.g. `"spotify"`) |
| `external_id` | `VARCHAR(255)` | NO | — | **PK (part 2)** — provider's own artist ID |
| `name` | `VARCHAR(500)` | NO | — | Artist / creator display name |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | Row creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | NO | `now()` | Last update timestamp |

**Keys & constraints**

| Type | Columns | Notes |
|---|---|---|
| Primary key | `(provider, external_id)` | Composite — enables multi-provider support |

---

## albums

Provider-agnostic album / release catalogue.

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| `provider` | `VARCHAR(50)` | NO | — | **PK (part 1)** — streaming provider slug |
| `external_id` | `VARCHAR(255)` | NO | — | **PK (part 2)** — provider's own album ID |
| `title` | `VARCHAR(500)` | NO | — | Album / release title |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | Row creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | NO | `now()` | Last update timestamp |

**Keys & constraints**

| Type | Columns | Notes |
|---|---|---|
| Primary key | `(provider, external_id)` | Composite — enables multi-provider support |

---

## tracks

Playable media items.  A track optionally belongs to an album.  The `media_type` column allows
future storage of video content in the same table.

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| `provider` | `VARCHAR(50)` | NO | — | **PK (part 1)** — streaming provider slug |
| `external_id` | `VARCHAR(255)` | NO | — | **PK (part 2)** — provider's own track/video ID |
| `title` | `VARCHAR(500)` | NO | — | Track / video title |
| `album_provider` | `VARCHAR(50)` | YES | `NULL` | FK (part 1) → `albums.provider` (SET NULL on delete) |
| `album_external_id` | `VARCHAR(255)` | YES | `NULL` | FK (part 2) → `albums.external_id` (SET NULL on delete) |
| `duration_ms` | `INTEGER` | YES | `NULL` | Track duration in milliseconds |
| `media_type` | `VARCHAR(50)` | NO | `'track'` | Content type: `"track"`, `"video"`, etc. |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | Row creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | NO | `now()` | Last update timestamp |

**Keys & constraints**

| Type | Columns | Notes |
|---|---|---|
| Primary key | `(provider, external_id)` | Composite — enables multi-provider support |
| Foreign key | `(album_provider, album_external_id)` → `(albums.provider, albums.external_id)` | ON DELETE SET NULL — album link is optional |

---

## track_artists

Many-to-many junction table linking tracks to their artists.  All four columns form the
composite primary key, which also implicitly prevents duplicate links.

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| `track_provider` | `VARCHAR(50)` | NO | — | **PK (part 1)** / FK → `tracks.provider` |
| `track_external_id` | `VARCHAR(255)` | NO | — | **PK (part 2)** / FK → `tracks.external_id` |
| `artist_provider` | `VARCHAR(50)` | NO | — | **PK (part 3)** / FK → `artists.provider` |
| `artist_external_id` | `VARCHAR(255)` | NO | — | **PK (part 4)** / FK → `artists.external_id` |

**Keys & constraints**

| Type | Columns | Notes |
|---|---|---|
| Primary key | `(track_provider, track_external_id, artist_provider, artist_external_id)` | Composite |
| Foreign key | `(track_provider, track_external_id)` → `(tracks.provider, tracks.external_id)` | ON DELETE CASCADE |
| Foreign key | `(artist_provider, artist_external_id)` → `(artists.provider, artists.external_id)` | ON DELETE CASCADE |

---

## play_events

One row per individual play event.  The unique constraint on
`(streaming_account_id, track_provider, track_external_id, played_at)` prevents duplicate
imports when the same recently-played window is polled more than once.

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid_generate_v4()` | **Primary key** |
| `streaming_account_id` | `UUID` | NO | — | **Foreign key** → `spotify_accounts.id` (CASCADE delete) |
| `track_provider` | `VARCHAR(50)` | NO | — | FK (part 1) → `tracks.provider` |
| `track_external_id` | `VARCHAR(255)` | NO | — | FK (part 2) → `tracks.external_id` |
| `played_at` | `TIMESTAMPTZ` | NO | — | Exact timestamp when the track was played |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | Row creation timestamp |

**Keys & constraints**

| Type | Columns | Notes |
|---|---|---|
| Primary key | `id` | |
| Foreign key | `streaming_account_id` → `spotify_accounts.id` | ON DELETE CASCADE |
| Foreign key | `(track_provider, track_external_id)` → `(tracks.provider, tracks.external_id)` | ON DELETE CASCADE |
| Unique | `(streaming_account_id, track_provider, track_external_id, played_at)` | `uq_play_events_account_track_time` — deduplicates repeated polls |

---

## Entity-relationship overview

```
users
 ├── spotify_accounts (user_id →)
 │    └── play_events (streaming_account_id →)
 │         └── tracks (track_provider + track_external_id →)
 │              ├── albums (album_provider + album_external_id →)
 │              └── track_artists (track_provider + track_external_id →)
 │                   └── artists (artist_provider + artist_external_id →)
 ├── ai_configs (user_id →)
 ├── analyses (user_id →, spotify_account_id →, ai_config_id →)
 │    ├── analysis_runs (analysis_id →)
 │    └── schedules (analysis_id →)
 └── schedules (user_id →)
```

---

## Notes

* All UUID primary keys default to a random v4 UUID.
* All timestamps are timezone-aware (`TIMESTAMPTZ` / `DateTime(timezone=True)`).
* `updated_at` columns are updated automatically via SQLAlchemy `onupdate` hooks.
* Encrypted columns (`encrypted_access_token`, `encrypted_refresh_token`, `encrypted_api_key`)
  contain Fernet-encrypted, base64-encoded ciphertext.  Use `crypto.encrypt()` /
  `crypto.decrypt()` in `backend/app/services/crypto.py` to read or write them.
* The `artists`, `albums`, and `tracks` tables use composite primary keys so that the same
  schema can accommodate multiple streaming providers (Spotify, YouTube, …) without conflicts.
