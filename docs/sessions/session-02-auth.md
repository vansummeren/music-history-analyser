# Session 02 — Authentication (SAML / OIDC)

## Goal
Implement authentication so that only users who authenticate through the configured SAML or OIDC
identity provider can access the application. On first login a user profile is automatically created.

## Prerequisite
Session 01 completed and merged.

## Scope
- SAML 2.0 support via `python3-saml`
- OIDC support via `Authlib` (configurable provider URL)
- Selection between SAML and OIDC via environment variable
- `User` model + Alembic migration
- JWT session tokens (short-lived access token + refresh token stored server-side in Redis)
- Auth router: `/api/auth/saml/*`, `/api/auth/oidc/*`, `/api/auth/logout`, `/api/auth/me`
- FastAPI dependency `get_current_user` used as guard on all protected routes
- Frontend: login redirect page, auth callback handler, protected route wrapper
- Logout flow (invalidates server-side refresh token)

## Acceptance Criteria
- Unauthenticated requests to `/api/users/me` return HTTP 401
- After successful OIDC login, `/api/auth/me` returns the user profile
- A new `users` row is created on first login
- Re-logging in with the same identity does NOT create a duplicate user
- Logout invalidates the token (subsequent requests with the same token return 401)
- All acceptance criteria covered by unit / integration tests

## Out of Scope
- Spotify linking
- AI configuration

## Key Files to Create / Modify

```
backend/
  app/models/user.py
  app/schemas/user.py
  app/routers/auth.py
  app/routers/users.py
  app/services/auth_service.py
  app/dependencies.py          # get_current_user dependency
  tests/test_auth.py

alembic/versions/<timestamp>_add_users.py

frontend/
  src/pages/LoginPage.tsx
  src/pages/AuthCallbackPage.tsx
  src/components/ProtectedRoute.tsx
  src/hooks/useAuth.ts
  src/services/authApi.ts
```
