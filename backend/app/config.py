from __future__ import annotations

from urllib.parse import urlparse, urlunparse

from pydantic_settings import BaseSettings, SettingsConfigDict


def mask_url(url: str) -> str:
    """Return *url* with any embedded password replaced by ``****``."""
    try:
        parsed = urlparse(url)
        if parsed.password:
            userinfo = f"{parsed.username}:****"
            host = parsed.hostname or ""
            if parsed.port:
                host = f"{host}:{parsed.port}"
            return urlunparse(parsed._replace(netloc=f"{userinfo}@{host}"))
    except Exception:
        pass
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    secret_key: str = "change-me-in-production"
    database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/musicanalyser"
    redis_url: str = "redis://redis:6379/0"
    backend_cors_origins: list[str] = ["http://localhost:3000"]

    # Auth
    auth_provider: str = "oidc"  # "oidc" | "saml"
    oidc_discovery_url: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    # Explicit redirect URI sent to the IdP.  Must match the value registered in the
    # IdP (e.g. https://your-app.example.com/api/auth/oidc/callback).
    # When empty the URI is auto-detected from the incoming request, which only works
    # correctly when running locally without a reverse proxy.
    oidc_redirect_uri: str = ""
    # Claim name in the OIDC userinfo/ID-token that contains the user's roles list
    oidc_roles_claim: str = "roles"
    saml_idp_metadata_url: str = ""
    saml_sp_entity_id: str = ""
    saml_sp_acs_url: str = ""
    # Attribute name in the SAML assertion that contains the user's roles list
    saml_roles_attribute: str = "roles"

    # Token lifetimes
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Frontend URL (used to build post-auth redirect)
    frontend_url: str = "http://localhost:3000"

    # Spotify
    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    spotify_redirect_uri: str = "http://localhost:8000/api/spotify/callback"

    # SMTP
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@example.com"
    smtp_tls: bool = True

    # Logging
    # Set to "DEBUG" to enable verbose log output for troubleshooting.
    # Accepted values: DEBUG, INFO, WARNING, ERROR, CRITICAL
    log_level: str = "INFO"

    # Build / version info (injected at image-build time via ARG → ENV)
    app_version: str = "0.1.0"
    build_number: str = "dev"
    build_date: str = "unknown"


settings = Settings()
