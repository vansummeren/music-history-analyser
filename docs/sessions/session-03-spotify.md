# Session 03 — Spotify Integration

**Status: ✅ Completed**

## Goal
Allow authenticated users to link one or more Spotify accounts, and retrieve their recent
listening history from the Spotify Web API.

## Prerequisite
Session 02 completed and merged.

## Scope
- Spotify OAuth 2.0 (Authorization Code + PKCE) flow
- `SpotifyAccount` model + Alembic migration
- Automatic token refresh
- Encrypted storage of access & refresh tokens (`cryptography.fernet`)
- Abstract `MusicProvider` base class (extensibility for future providers)
- Spotify adapter implementing `MusicProvider`
- API endpoints:
  - `POST /api/spotify/link` — initiate OAuth flow
  - `GET  /api/spotify/callback` — OAuth callback
  - `GET  /api/spotify/accounts` — list linked accounts
  - `DELETE /api/spotify/accounts/{id}` — unlink account
  - `GET  /api/spotify/accounts/{id}/history` — fetch recent tracks (with `time_window` param)
- Frontend: Spotify account management page with connect / disconnect actions

## Acceptance Criteria
- User can link a Spotify account via OAuth
- User can unlink a Spotify account
- User can fetch recent listening history (list of tracks with artist, title, played_at)
- Token refresh happens transparently when access token expires
- Tokens stored in DB are encrypted (not plaintext)
- Another user cannot access a Spotify account they do not own (403)
- All flows covered by unit tests with mocked Spotify API calls

## Out of Scope
- AI analysis
- Scheduling

## Key Files to Create / Modify

```
backend/
  app/models/spotify_account.py
  app/schemas/spotify.py
  app/routers/spotify.py
  app/services/music/__init__.py   # MusicProvider ABC
  app/services/music/spotify.py    # Spotify adapter
  app/services/crypto.py           # fernet encrypt/decrypt helpers
  tests/test_spotify.py

alembic/versions/<timestamp>_add_spotify_accounts.py

frontend/
  src/pages/SpotifyAccountsPage.tsx
  src/components/SpotifyAccountCard.tsx
  src/services/spotifyApi.ts
```
