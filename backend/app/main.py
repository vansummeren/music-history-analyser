from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import mask_url, settings
from app.middleware import SecurityHeadersMiddleware
from app.routers.ai_configs import router as ai_configs_router
from app.routers.analyses import router as analyses_router
from app.routers.auth import router as auth_router
from app.routers.schedules import router as schedules_router
from app.routers.spotify import router as spotify_router
from app.routers.users import router as users_router

logger = logging.getLogger(__name__)


def _log_startup() -> None:
    """Emit an INFO-level banner with non-sensitive startup configuration."""
    sep = "=" * 54
    lines: list[str] = [
        "",
        sep,
        "  Music History Analyser – Backend starting",
        sep,
        f"  Version             : {settings.app_version}",
        f"  Build               : #{settings.build_number}  ({settings.build_date})",
        sep,
    ]

    # ── Authentication ────────────────────────────────────────
    provider = settings.auth_provider.upper()
    lines.append(f"  Authentication      : {provider}")
    if settings.auth_provider == "oidc":
        lines.append(f"    Discovery URL     : {settings.oidc_discovery_url or '(not set)'}")
        lines.append(f"    Client ID         : {settings.oidc_client_id or '(not set)'}")
        lines.append(f"    Roles claim       : {settings.oidc_roles_claim}")
    else:
        lines.append(f"    IdP metadata URL  : {settings.saml_idp_metadata_url or '(not set)'}")
        lines.append(f"    SP entity ID      : {settings.saml_sp_entity_id or '(not set)'}")
        lines.append(f"    SP ACS URL        : {settings.saml_sp_acs_url or '(not set)'}")
        lines.append(f"    Roles attribute   : {settings.saml_roles_attribute}")

    # ── Infrastructure ────────────────────────────────────────
    lines.append(f"  Database            : {mask_url(settings.database_url)}")
    lines.append(f"  Redis / broker      : {mask_url(settings.redis_url)}")

    # ── Application ───────────────────────────────────────────
    lines.append(f"  CORS origins        : {settings.backend_cors_origins}")
    lines.append(f"  Frontend URL        : {settings.frontend_url}")

    # ── Spotify ───────────────────────────────────────────────
    spotify_configured = "yes" if settings.spotify_client_id else "no"
    lines.append("  Spotify")
    lines.append(f"    Redirect URI      : {settings.spotify_redirect_uri}")
    lines.append(f"    Client configured : {spotify_configured}")

    # ── SMTP ──────────────────────────────────────────────────
    tls_label = "enabled" if settings.smtp_tls else "disabled"
    smtp_creds = "configured" if settings.smtp_password else "not set"
    lines.append("  SMTP")
    smtp_host_info = f"{settings.smtp_host}:{settings.smtp_port}  (TLS: {tls_label})"
    lines.append(f"    Host              : {smtp_host_info}")
    lines.append(f"    From              : {settings.smtp_from}")
    lines.append(f"    Credentials       : {smtp_creds}")

    # ── Token lifetimes ───────────────────────────────────────
    lines.append(
        f"  Token lifetimes     : access {settings.access_token_expire_minutes} min"
        f"  |  refresh {settings.refresh_token_expire_days} days"
    )

    lines.append(sep)
    logger.info("\n".join(lines))


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    _log_startup()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Music History Analyser",
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=_lifespan,
    )

    # Security headers must be added before CORS so they are always present
    app.add_middleware(SecurityHeadersMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.backend_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(spotify_router)
    app.include_router(ai_configs_router)
    app.include_router(analyses_router)
    app.include_router(schedules_router)

    @app.get("/api/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
