from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    saml_idp_metadata_url: str = ""
    saml_sp_entity_id: str = ""
    saml_sp_acs_url: str = ""

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


settings = Settings()
