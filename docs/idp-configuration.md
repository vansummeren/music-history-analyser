# Identity Provider Configuration

This document explains how to configure the supported identity providers (IdPs).
The application supports two authentication protocols: **OIDC** (OpenID Connect) and
**SAML 2.0**.  Choose one by setting `AUTH_PROVIDER=oidc` or `AUTH_PROVIDER=saml`.

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

# Name of the claim in the userinfo / ID-token that contains the roles list.
# Defaults to "roles".  Change this to match your IdP (see IdP-specific sections below).
OIDC_ROLES_CLAIM=roles
```

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
OIDC_ROLES_CLAIM=groups
```

### Keycloak (OIDC)

```env
OIDC_DISCOVERY_URL=https://<keycloak-host>/realms/<realm>/.well-known/openid-configuration
OIDC_CLIENT_ID=<client-id>
OIDC_CLIENT_SECRET=<client-secret>
OIDC_ROLES_CLAIM=roles
```

Add a **mapper** of type *User Realm Role* or *User Client Role* so that roles appear
in the `roles` claim of the userinfo response.

### Azure AD / Entra ID (OIDC)

```env
OIDC_DISCOVERY_URL=https://login.microsoftonline.com/<tenant-id>/v2.0/.well-known/openid-configuration
OIDC_CLIENT_ID=<application-id>
OIDC_CLIENT_SECRET=<client-secret>
OIDC_ROLES_CLAIM=roles
```

Define **App Roles** in the Azure portal and assign them to users / groups.  Azure
includes them in the `roles` claim automatically.

### Okta (OIDC)

```env
OIDC_DISCOVERY_URL=https://<okta-domain>/oauth2/default/.well-known/openid-configuration
OIDC_CLIENT_ID=<client-id>
OIDC_CLIENT_SECRET=<client-secret>
OIDC_ROLES_CLAIM=groups   # or the custom claim name you configured
```

Add a **Groups claim** to the authorization server in Okta and filter the groups you
want to expose.

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
