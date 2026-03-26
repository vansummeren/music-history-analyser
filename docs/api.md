# API Reference

> This document is auto-generated from the FastAPI OpenAPI schema during the deploy pipeline.
> The authoritative interactive docs are available at `http://localhost:8000/docs` when the
> backend is running locally.

## Base URL

```
http://localhost:8000/api   (local development)
https://<your-domain>/api   (production)
```

## Authentication

All endpoints except the auth callbacks require a valid JWT `Bearer` token in the
`Authorization` header.

```
Authorization: Bearer <access_token>
```

Tokens are issued after a successful SAML / OIDC login and expire after 15 minutes.
Use `POST /api/auth/refresh` with a valid refresh token to obtain a new access token.

---

## Endpoints (summary)

### Auth

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/auth/oidc/login` | Redirect to OIDC provider |
| `GET` | `/api/auth/oidc/callback` | OIDC callback |
| `GET` | `/api/auth/saml/login` | Redirect to SAML IdP |
| `POST` | `/api/auth/saml/acs` | SAML Assertion Consumer Service |
| `POST` | `/api/auth/refresh` | Refresh access token |
| `POST` | `/api/auth/logout` | Invalidate tokens |
| `GET` | `/api/auth/me` | Current user profile |

### Users

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/users/me` | Get own profile |
| `PATCH` | `/api/users/me` | Update display name |

### Spotify Accounts

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/spotify/link` | Start OAuth flow |
| `GET` | `/api/spotify/callback` | OAuth callback |
| `GET` | `/api/spotify/accounts` | List linked accounts |
| `DELETE` | `/api/spotify/accounts/{id}` | Unlink account |
| `GET` | `/api/spotify/accounts/{id}/history` | Fetch listening history |

### AI Configurations

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/ai-configs` | Add AI config |
| `GET` | `/api/ai-configs` | List AI configs |
| `DELETE` | `/api/ai-configs/{id}` | Remove AI config |

### Analyses

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/analyses` | Create analysis |
| `GET` | `/api/analyses` | List analyses |
| `DELETE` | `/api/analyses/{id}` | Delete analysis |
| `POST` | `/api/analyses/{id}/run` | Trigger immediate run |
| `GET` | `/api/analyses/{id}/runs` | List past runs |
| `GET` | `/api/analyses/{id}/runs/{run_id}` | Get run detail |

### Schedules

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/schedules` | Create schedule |
| `GET` | `/api/schedules` | List schedules |
| `PATCH` | `/api/schedules/{id}` | Update schedule |
| `DELETE` | `/api/schedules/{id}` | Delete schedule |

### Health

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Liveness check |

---

_Full request / response schemas are documented in the interactive OpenAPI UI._
