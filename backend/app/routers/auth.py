"""Auth router — OIDC, SAML, logout, and /me."""
from __future__ import annotations

import secrets
import urllib.parse
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.redis_client import get_redis
from app.schemas.user import UserRead
from app.services import auth_service
from app.services.rate_limit import rate_limit

router = APIRouter(prefix="/api/auth", tags=["auth"])

# ── Rate-limit dependency (20 requests / 60 s per IP) ────────────────────────


async def _login_rate_limit(
    request: Request,
    redis: Any = Depends(get_redis),
) -> None:
    await rate_limit(request, redis, limit=20, window=60, key_prefix="rl:login")

_bearer = HTTPBearer(auto_error=False)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _frontend_callback(access_token: str, refresh_token: str) -> str:
    """Build the frontend callback URL that carries the issued tokens."""
    return (
        f"{settings.frontend_url}/auth/callback"
        f"#access_token={access_token}&refresh_token={refresh_token}"
    )


# ── Provider dispatcher ───────────────────────────────────────────────────────


@router.get("/login", dependencies=[Depends(_login_rate_limit)])
async def login_dispatch() -> RedirectResponse:
    """Redirect to the login endpoint for the configured auth provider.

    Using this URL insulates the frontend from needing to know which provider
    (OIDC or SAML) is active.  Change ``AUTH_PROVIDER`` in the environment and
    restart the backend — no frontend change required.
    """
    if settings.auth_provider == "saml":
        return RedirectResponse("/api/auth/saml/login")
    return RedirectResponse("/api/auth/oidc/login")


# ── OIDC ─────────────────────────────────────────────────────────────────────


@router.get("/oidc/login", dependencies=[Depends(_login_rate_limit)])
async def oidc_login(
    request: Request,
    redis: Any = Depends(get_redis),
) -> RedirectResponse:
    """Redirect the browser to the OIDC IdP authorization endpoint."""
    if not settings.oidc_discovery_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OIDC is not configured",
        )
    config = await auth_service.fetch_oidc_discovery(settings.oidc_discovery_url)
    state = secrets.token_hex(16)
    nonce = secrets.token_hex(16)
    await auth_service.store_oidc_state(state, nonce, redis)

    redirect_uri = str(request.url_for("oidc_callback"))
    auth_url = (
        f"{config['authorization_endpoint']}"
        f"?response_type=code"
        f"&client_id={urllib.parse.quote(settings.oidc_client_id)}"
        f"&redirect_uri={urllib.parse.quote(redirect_uri)}"
        f"&scope=openid+email+profile"
        f"&state={state}"
        f"&nonce={nonce}"
    )
    return RedirectResponse(auth_url)


@router.get("/oidc/callback", name="oidc_callback")
async def oidc_callback(
    code: str,
    state: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Any = Depends(get_redis),
) -> RedirectResponse:
    """Handle the OIDC authorization-code callback from the IdP."""
    nonce = await auth_service.pop_oidc_state(state, redis)
    if nonce is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired state parameter",
        )

    config = await auth_service.fetch_oidc_discovery(settings.oidc_discovery_url)
    redirect_uri = str(request.url_for("oidc_callback"))

    token_data = await auth_service.exchange_oidc_code(
        config["token_endpoint"], code, redirect_uri
    )
    userinfo = await auth_service.fetch_oidc_userinfo(
        config["userinfo_endpoint"], token_data["access_token"]
    )

    idp_roles = auth_service.extract_oidc_roles(userinfo)
    role = auth_service.resolve_role(idp_roles)

    user = await auth_service.upsert_user(
        db,
        sub=userinfo["sub"],
        provider="oidc",
        email=userinfo.get("email"),
        display_name=userinfo.get("name") or userinfo.get("preferred_username"),
        role=role,
    )

    access_token = auth_service.create_access_token(user.id)
    refresh_token = await auth_service.create_refresh_token(user.id, redis)
    return RedirectResponse(_frontend_callback(access_token, refresh_token))


# ── SAML ──────────────────────────────────────────────────────────────────────


def _build_saml_auth(request_data: dict[str, Any]) -> Any:
    """Construct a ``OneLogin_Saml2_Auth`` instance from a prepared request dict.

    The import is deferred so that environments without the native xmlsec1
    library can still run the OIDC-only code paths.
    """
    try:
        from onelogin.saml2.auth import OneLogin_Saml2_Auth
        from onelogin.saml2.idp_metadata_parser import (
            OneLogin_Saml2_IdPMetadataParser,
        )
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SAML support is not available in this environment",
        ) from exc

    idp_data: dict[str, Any] = {}
    if settings.saml_idp_metadata_url:
        idp_data = OneLogin_Saml2_IdPMetadataParser.parse_remote(
            settings.saml_idp_metadata_url
        )

    saml_settings: dict[str, Any] = {
        "strict": True,
        "debug": False,
        "sp": {
            "entityId": settings.saml_sp_entity_id,
            "assertionConsumerService": {
                "url": settings.saml_sp_acs_url,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
            },
        },
        **idp_data,
    }
    return OneLogin_Saml2_Auth(request_data, saml_settings)


async def _prepare_saml_request(request: Request) -> dict[str, Any]:
    form_data: dict[str, str] = {}
    if request.method == "POST":
        form = await request.form()
        form_data = {k: str(v) for k, v in form.items()}
    return {
        "https": "on" if request.url.scheme == "https" else "off",
        "http_host": request.headers.get("host", "localhost"),
        "script_name": request.url.path,
        "get_data": dict(request.query_params),
        "post_data": form_data,
    }


@router.get("/saml/login", dependencies=[Depends(_login_rate_limit)])
async def saml_login(request: Request) -> RedirectResponse:
    """Redirect the browser to the SAML IdP."""
    if not settings.saml_sp_entity_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SAML is not configured",
        )
    req = await _prepare_saml_request(request)
    auth = _build_saml_auth(req)
    login_url: str = auth.login()
    return RedirectResponse(login_url)


@router.post("/saml/acs", dependencies=[Depends(_login_rate_limit)])
async def saml_acs(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Any = Depends(get_redis),
) -> HTMLResponse:
    """Assertion Consumer Service — validate the SAML response and log the user in.

    Returns a self-submitting HTML page that stores the tokens and redirects to
    the frontend, because the IdP POST lands here (not on the frontend origin).
    """
    req = await _prepare_saml_request(request)
    auth = _build_saml_auth(req)
    auth.process_response()

    errors = auth.get_errors()
    if errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"SAML error: {', '.join(errors)}",
        )

    attributes: dict[str, Any] = auth.get_attributes()
    name_id: str = auth.get_nameid()

    email_vals: list[str] = attributes.get("email", []) or attributes.get(
        "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress", []
    )
    name_vals: list[str] = attributes.get("displayName", []) or attributes.get(
        "http://schemas.microsoft.com/identity/claims/displayname", []
    )

    idp_roles = auth_service.extract_saml_roles(attributes)
    role = auth_service.resolve_role(idp_roles)

    user = await auth_service.upsert_user(
        db,
        sub=name_id,
        provider="saml",
        email=email_vals[0] if email_vals else None,
        display_name=name_vals[0] if name_vals else None,
        role=role,
    )

    access_token = auth_service.create_access_token(user.id)
    refresh_token = await auth_service.create_refresh_token(user.id, redis)
    callback_url = _frontend_callback(access_token, refresh_token)

    # The IdP sent a POST, so we cannot just issue an HTTP redirect. Return a
    # tiny HTML page that navigates the browser to the frontend callback URL.
    html = f"""<!doctype html>
<html><head><meta charset="utf-8">
<script>window.location.replace({callback_url!r});</script>
</head><body>Redirecting…</body></html>"""
    return HTMLResponse(html)


# ── Common ────────────────────────────────────────────────────────────────────


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


@router.post("/logout")
async def logout(
    body: LogoutRequest,
    request: Request,
    redis: Any = Depends(get_redis),
) -> dict[str, str]:
    """Revoke the current access token and optionally the refresh token."""
    credentials: HTTPAuthorizationCredentials | None = await _bearer(request)
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    await auth_service.revoke_access_token(credentials.credentials, redis)
    if body.refresh_token:
        await auth_service.revoke_refresh_token(body.refresh_token, redis)
    return {"detail": "logged out"}


@router.get("/me")
async def me(user: User = Depends(get_current_user)) -> UserRead:
    """Return the profile of the currently authenticated user."""
    return UserRead.model_validate(user)
