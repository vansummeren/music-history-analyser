# Session 02 — Authentication (SAML / OIDC)

**Status: ✅ Completed**

## Goal
Implement authentication so that only users who authenticate through the configured SAML or OIDC
identity provider can access the application. On first login a user profile is automatically created.

## Prerequisite
Session 01 completed and merged.

## Scope
- SAML 2.0 support via `python3-saml`
- OIDC support via `Authlib` (configurable provider URL)
- Selection between SAML and OIDC via environment variable
- `User` model + Alembic migration (includes `role` field synced from IdP on every login)
- JWT session tokens (short-lived access token + refresh token stored server-side in Redis)
- Auth router: `/api/auth/saml/*`, `/api/auth/oidc/*`, `/api/auth/logout`, `/api/auth/me`
- FastAPI dependency `get_current_user` used as guard on all protected routes
- FastAPI dependency `require_role(role)` for role-gated routes (ready for future use)
- Frontend: login redirect page, auth callback handler, protected route wrapper
- Logout flow (invalidates server-side refresh token)
- Role sync from IdP on every login (`"user"` / `"admin"`)

## Supported Identity Providers

See **[docs/idp-configuration.md](../idp-configuration.md)** for full setup instructions.

| IdP | OIDC | SAML |
|---|---|---|
| Authentik | ✅ | ✅ |
| Keycloak | ✅ | ✅ |
| Azure AD / Entra ID | ✅ | ✅ |
| Okta | ✅ | ✅ |
| Google Workspace | ✅ | — |
| Any OIDC-compliant IdP | ✅ | — |
| Any SAML 2.0–compliant IdP | — | ✅ |

## Acceptance Criteria
- ✅ Unauthenticated requests to `/api/users/me` return HTTP 401
- ✅ After successful OIDC login, `/api/auth/me` returns the user profile
- ✅ A new `users` row is created on first login
- ✅ Re-logging in with the same identity does NOT create a duplicate user
- ✅ Logout invalidates the token (subsequent requests with the same token return 401)
- ✅ Role is synced from the IdP on every login
- ✅ All acceptance criteria covered by unit / integration tests

## Out of Scope
- Spotify linking
- AI configuration

## Key Files Created / Modified

```
backend/
  app/models/user.py            ← User model (id, sub, provider, email, display_name, role)
  app/schemas/user.py           ← UserRead schema
  app/routers/auth.py           ← /api/auth/* endpoints
  app/routers/users.py          ← /api/users/me
  app/services/auth_service.py  ← JWT, tokens, OIDC helpers, upsert_user, role resolution
  app/dependencies.py           ← get_current_user, require_role
  app/redis_client.py           ← shared async Redis pool
  tests/conftest.py             ← SQLite + FakeRedis fixtures
  tests/test_auth.py            ← auth acceptance tests

alembic/versions/20260326_001_add_users.py

frontend/
  src/pages/LoginPage.tsx
  src/pages/AuthCallbackPage.tsx
  src/components/ProtectedRoute.tsx
  src/hooks/useAuth.ts
  src/services/authApi.ts

docs/idp-configuration.md      ← IdP setup guide (Authentik, Keycloak, Azure AD, Okta, …)
```
