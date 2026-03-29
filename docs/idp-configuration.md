# Identity Provider Configuration

This document explains how to configure the supported identity providers (IdPs).
The application supports two authentication protocols: **OIDC** (OpenID Connect) and
**SAML 2.0**.  Choose one by setting `AUTH_PROVIDER=oidc` or `AUTH_PROVIDER=saml`.

---

## How authentication works

### OIDC flow

```
Browser          Backend                    IdP
  │                 │                         │
  │  GET /api/auth/oidc/login                 │
  │ ──────────────> │                         │
  │                 │  Redirect to IdP        │
  │ <─────────────  │ ──────────────────────> │
  │                 │                         │
  │  User authenticates with IdP              │
  │ <─────────────────────────────────────── │
  │  GET /api/auth/oidc/callback?code=...    │
  │ ──────────────> │                         │
  │                 │  Exchange code → tokens │
  │                 │ ──────────────────────> │
  │                 │ <────────────────────── │
  │                 │  Fetch userinfo         │
  │                 │ ──────────────────────> │
  │                 │ <────────────────────── │
  │                 │  Upsert user in DB      │
  │                 │  Issue JWT access +     │
  │                 │  refresh tokens         │
  │  Redirect → /auth/callback#access_token=…│
  │ <─────────────  │                         │
  │  Store tokens in localStorage             │
```

### SAML 2.0 flow

```
Browser          Backend               IdP
  │                 │                    │
  │  GET /api/auth/saml/login            │
  │ ──────────────> │                    │
  │                 │  Redirect to IdP   │
  │ <─────────────  │ ─────────────────> │
  │                 │                    │
  │  User authenticates with IdP         │
  │ <────────────────────────────────── │
  │  POST /api/auth/saml/acs             │
  │   (SAMLResponse in form body)        │
  │ ──────────────> │                    │
  │                 │  Validate assertion│
  │                 │  Upsert user in DB │
  │                 │  Issue JWT tokens  │
  │  HTML meta-refresh → /auth/callback  │
  │ <─────────────  │                    │
  │  Store tokens in localStorage        │
```

---

## Supported IdPs

| Identity Provider | OIDC | SAML | Notes |
|---|---|---|---|
| **Authentik** | ✅ | ✅ | Roles claim is `groups` by default |
| **Keycloak** | ✅ | ✅ | Roles claim is `roles` by default |
| **Azure AD / Entra ID** | ✅ | ✅ | Roles claim is `roles` (app roles) |
| **Okta** | ✅ | ✅ | Roles delivered via a custom claim |
| **Google Workspace** | ✅ | — | No native roles claim; all users get `user` |
| Any OIDC-compliant IdP | ✅ | — | Configure `OIDC_ROLES_CLAIM` for your claim name |
| Any SAML 2.0–compliant IdP | — | ✅ | Configure `SAML_ROLES_ATTRIBUTE` for your attribute |

---

## Role mapping

Roles are **re-synced on every login**.  The IdP delivers a list of role strings;
the app maps them to its two internal roles:

| IdP role contains `"admin"` (case-insensitive) | Internal role |
|---|---|
| Yes | `admin` |
| No / empty | `user` |

---

## OIDC configuration

```env
AUTH_PROVIDER=oidc
OIDC_DISCOVERY_URL=https://<idp-host>/.well-known/openid-configuration
OIDC_CLIENT_ID=<client-id>
OIDC_CLIENT_SECRET=<client-secret>

# REQUIRED in production.  The exact redirect URI you registered with your IdP.
# Must point to <public-app-url>/api/auth/oidc/callback.
# When left blank the URI is auto-detected from the incoming request — this only
# works in local development where no reverse proxy is involved.
OIDC_REDIRECT_URI=https://your-app.example.com/api/auth/oidc/callback

# Name of the claim in the userinfo / ID-token that contains the roles list.
# Defaults to "roles".  Change this to match your IdP (see IdP-specific sections below).
OIDC_ROLES_CLAIM=roles
```

> ⚠️ **`OIDC_REDIRECT_URI` is required in any environment where a reverse proxy
> (nginx, Cloudflare Tunnel, load balancer) sits in front of the backend.**  Without
> it the backend generates the URI from the incoming request URL, which will be an
> internal address that does not match the URI registered with your IdP.

### Authentik (OIDC)

1. In Authentik → **Applications** → create a new application and provider of type
   *OAuth2/OpenID Connect*.
2. Set the **Redirect URI** to `https://<your-app>/api/auth/oidc/callback`.
3. Under **Advanced protocol settings**, add a **Property Mapping** that exposes groups
   (e.g. the built-in *OAuth Mapping: OpenID 'groups'* scope).
4. Note that Authentik exposes groups under the `groups` claim, so set:

```env
OIDC_DISCOVERY_URL=https://<authentik-host>/application/o/<app-slug>/.well-known/openid-configuration
OIDC_CLIENT_ID=<client-id>
OIDC_CLIENT_SECRET=<client-secret>
OIDC_REDIRECT_URI=https://<your-app>/api/auth/oidc/callback
OIDC_ROLES_CLAIM=groups
```

### Keycloak (OIDC)

1. Create a new client in Keycloak → *Clients* → *Create client*.
2. Set the redirect URI to `https://<your-app>/api/auth/oidc/callback`.
3. Add a **mapper** of type *User Realm Role* or *User Client Role* so that roles appear
   in the `roles` claim of the userinfo response.

```env
OIDC_DISCOVERY_URL=https://<keycloak-host>/realms/<realm>/.well-known/openid-configuration
OIDC_CLIENT_ID=<client-id>
OIDC_CLIENT_SECRET=<client-secret>
OIDC_REDIRECT_URI=https://<your-app>/api/auth/oidc/callback
OIDC_ROLES_CLAIM=roles
```

### Azure AD / Entra ID (OIDC)

1. Register an app in the Azure portal.
2. Under *Authentication*, add `https://<your-app>/api/auth/oidc/callback` as a
   redirect URI (type: *Web*).
3. Define **App Roles** and assign them to users/groups.
   Azure includes them in the `roles` claim automatically.

```env
OIDC_DISCOVERY_URL=https://login.microsoftonline.com/<tenant-id>/v2.0/.well-known/openid-configuration
OIDC_CLIENT_ID=<application-id>
OIDC_CLIENT_SECRET=<client-secret>
OIDC_REDIRECT_URI=https://<your-app>/api/auth/oidc/callback
OIDC_ROLES_CLAIM=roles
```

### Okta (OIDC)

1. Create a new app integration in Okta → *Applications* → *Create App Integration*.
2. Choose *OIDC - OpenID Connect* / *Web Application*.
3. Add `https://<your-app>/api/auth/oidc/callback` as the sign-in redirect URI.
4. Add a **Groups claim** to the authorization server and filter the groups you want
   to expose.

```env
OIDC_DISCOVERY_URL=https://<okta-domain>/oauth2/default/.well-known/openid-configuration
OIDC_CLIENT_ID=<client-id>
OIDC_CLIENT_SECRET=<client-secret>
OIDC_REDIRECT_URI=https://<your-app>/api/auth/oidc/callback
OIDC_ROLES_CLAIM=groups   # or the custom claim name you configured
```

---

## SAML 2.0 configuration

```env
AUTH_PROVIDER=saml
SAML_IDP_METADATA_URL=https://<idp-host>/metadata.xml
SAML_SP_ENTITY_ID=https://<your-app>
SAML_SP_ACS_URL=https://<your-app>/api/auth/saml/acs

# Name of the attribute in the SAML assertion that contains the roles list.
# Defaults to "roles".
SAML_ROLES_ATTRIBUTE=roles
```

**SP metadata values registered with the IdP:**

| Field | Value |
|---|---|
| Entity ID / Issuer | value of `SAML_SP_ENTITY_ID` |
| ACS URL (POST binding) | value of `SAML_SP_ACS_URL` — must end in `/api/auth/saml/acs` |

### Authentik (SAML)

1. In Authentik → **Applications** → create a new application and provider of type *SAML*.
2. Set **ACS URL** to `https://<your-app>/api/auth/saml/acs`.
3. Set **Issuer** to `https://<your-app>` (must match `SAML_SP_ENTITY_ID`).
4. Add a **Property Mapping** to include groups in the assertion, then set:

```env
SAML_IDP_METADATA_URL=https://<authentik-host>/api/v3/providers/saml/<id>/metadata/?download
SAML_SP_ENTITY_ID=https://<your-app>
SAML_SP_ACS_URL=https://<your-app>/api/auth/saml/acs
SAML_ROLES_ATTRIBUTE=groups
```

### Keycloak (SAML)

1. Create a SAML client in Keycloak → *Clients* → *Create client* → choose *SAML*.
2. Set *Root URL* to `https://<your-app>`.
3. Set *Valid Redirect URIs* to include `https://<your-app>/api/auth/saml/acs`.
4. Set *Master SAML Processing URL* to `https://<your-app>/api/auth/saml/acs`.
5. Add a mapper of type *Role list* to include roles in the assertion.

```env
SAML_IDP_METADATA_URL=https://<keycloak-host>/realms/<realm>/protocol/saml/descriptor
SAML_SP_ENTITY_ID=https://<your-app>
SAML_SP_ACS_URL=https://<your-app>/api/auth/saml/acs
SAML_ROLES_ATTRIBUTE=roles
```

### Azure AD / Entra ID (SAML)

1. In Azure portal → *Enterprise Applications* → *New application* → *Create your own
   application* → choose *non-gallery*.
2. Under *Single sign-on* choose *SAML*.
3. Set the *Identifier (Entity ID)* to the value of `SAML_SP_ENTITY_ID`.
4. Set the *Reply URL (ACS URL)* to the value of `SAML_SP_ACS_URL`.
5. Add app roles in *App registrations* → *App roles* and assign them to users/groups.

```env
SAML_IDP_METADATA_URL=https://login.microsoftonline.com/<tenant-id>/federationmetadata/2007-06/federationmetadata.xml
SAML_SP_ENTITY_ID=https://<your-app>
SAML_SP_ACS_URL=https://<your-app>/api/auth/saml/acs
SAML_ROLES_ATTRIBUTE=roles
```

---

## Production checklist

Before going live, verify the following:

- [ ] `SECRET_KEY` is a random 64-character hex string (not the default placeholder).
- [ ] `FRONTEND_URL` is set to the public URL of the frontend (e.g. `https://your-app.example.com`).
- [ ] For **OIDC**: `OIDC_REDIRECT_URI` is set to `https://<your-app>/api/auth/oidc/callback`.
      The same URI must be registered as an allowed redirect URI in your IdP.
- [ ] For **SAML**: `SAML_SP_ACS_URL` is set to `https://<your-app>/api/auth/saml/acs`.
      The same URL must be registered as the ACS URL in your IdP.
- [ ] `BACKEND_CORS_ORIGINS` includes the public frontend URL.
- [ ] The IdP's metadata / client configuration points to the **public** domain, not to
      internal Docker hostnames.

---

## Troubleshooting

### OIDC: "redirect_uri_mismatch" or "Invalid redirect URI"

The `redirect_uri` sent to the IdP does not match any URI registered in the IdP.

**Root cause**: `OIDC_REDIRECT_URI` is not set so the backend auto-detects the URI
from the incoming request.  Behind a reverse proxy the detected URI will be the
internal address (e.g. `http://localhost:8000/api/auth/oidc/callback`) rather than
the public one.

**Fix**: set `OIDC_REDIRECT_URI=https://<your-app>/api/auth/oidc/callback` in `.env`
and register the same URI in the IdP.

---

### OIDC: State parameter invalid or expired

The OIDC `state` value stored in Redis during `/oidc/login` was not found when the IdP
redirected back to `/oidc/callback`.

**Possible causes:**
* The `state` parameter in the callback URL does not match the stored value (CSRF
  attempt or replay attack — harmless, reject the request).
* The Redis key expired (default TTL: 10 minutes).  The user took longer than 10 minutes
  to complete the IdP login.
* Redis was restarted between the login and callback requests.

---

### SAML: Assertion validation fails

Common reasons for SAML assertion validation errors:

| Error | Cause | Fix |
|---|---|---|
| `invalid_response` | Clock skew > 5 minutes between SP and IdP | Synchronize server clocks (NTP) |
| `wrong_acs` | ACS URL in assertion ≠ `SAML_SP_ACS_URL` | Check both values match exactly |
| `invalid_logout` | Signature mismatch | Verify the IdP certificate in the metadata URL is current |

---

### Post-login redirect lands on a blank page or 404

**Root cause**: `FRONTEND_URL` is not set or is set to an incorrect value.  The backend
builds the post-auth redirect as `{FRONTEND_URL}/auth/callback#access_token=…`.

**Fix**: set `FRONTEND_URL=https://<your-app>` in `.env`.  The value must be the
origin users access in their browser, with no trailing slash.

