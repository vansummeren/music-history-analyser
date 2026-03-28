"""Authentication service — JWT, token lifecycle, user upsert, IdP helpers."""
from __future__ import annotations

import logging
import secrets
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
from authlib.jose import jwt
from authlib.jose.errors import JoseError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User

logger = logging.getLogger(__name__)

# ── Redis key prefixes ────────────────────────────────────────────────────────
_REFRESH_PREFIX = "refresh:"
_REVOKE_PREFIX = "revoked:"
_OIDC_STATE_PREFIX = "oidc_state:"

# ── Minimal Redis protocol used by this service ───────────────────────────────
# We type the redis parameter as Any so the real redis.asyncio.Redis client and
# in-test dict-backed fakes are both accepted without pulling redis into the
# module-level type graph for tests that don't need it.

# ── JWT ───────────────────────────────────────────────────────────────────────


def create_access_token(user_id: uuid.UUID) -> str:
    """Return a signed JWT access token for *user_id*."""
    now = int(datetime.now(UTC).timestamp())
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + settings.access_token_expire_minutes * 60,
        "type": "access",
    }
    # authlib 1.x jwt.encode always returns bytes; decode to a str for transport.
    token_bytes: bytes = jwt.encode({"alg": "HS256"}, payload, settings.secret_key)
    return token_bytes.decode()


def verify_access_token(token: str) -> uuid.UUID | None:
    """Decode and validate *token*; return the user UUID or None on failure."""
    try:
        claims = jwt.decode(token, settings.secret_key)
        claims.validate()
        if claims.get("type") != "access":
            return None
        return uuid.UUID(claims["sub"])
    except (JoseError, ValueError, KeyError):
        return None


# ── Refresh token ─────────────────────────────────────────────────────────────


async def create_refresh_token(user_id: uuid.UUID, redis: Any) -> str:
    token = secrets.token_hex(32)
    ttl = settings.refresh_token_expire_days * 86400
    await redis.set(f"{_REFRESH_PREFIX}{token}", str(user_id), ex=ttl)
    return token


async def revoke_refresh_token(refresh_token: str, redis: Any) -> None:
    await redis.delete(f"{_REFRESH_PREFIX}{refresh_token}")


# ── Access-token revocation (blocklist) ───────────────────────────────────────


async def revoke_access_token(access_token: str, redis: Any) -> None:
    """Add *access_token* to the revocation blocklist for its remaining TTL."""
    try:
        claims = jwt.decode(access_token, settings.secret_key)
        claims.validate()
        exp = int(claims["exp"])
        now = int(datetime.now(UTC).timestamp())
        remaining = max(exp - now, 1)
        await redis.set(f"{_REVOKE_PREFIX}{access_token}", "1", ex=remaining)
        logger.info("Access token revoked (TTL: %ds)", remaining)
    except (JoseError, KeyError):
        pass


async def is_token_revoked(access_token: str, redis: Any) -> bool:
    result = await redis.get(f"{_REVOKE_PREFIX}{access_token}")
    return result is not None


# ── OIDC state management ─────────────────────────────────────────────────────


async def store_oidc_state(state: str, nonce: str, redis: Any, ttl: int = 600) -> None:
    await redis.set(f"{_OIDC_STATE_PREFIX}{state}", nonce, ex=ttl)


async def pop_oidc_state(state: str, redis: Any) -> str | None:
    """Return and delete the nonce for *state*, or None if not found."""
    key = f"{_OIDC_STATE_PREFIX}{state}"
    nonce = await redis.get(key)
    if nonce is None:
        return None
    await redis.delete(key)
    return nonce.decode() if isinstance(nonce, bytes) else str(nonce)


# ── OIDC external HTTP helpers ────────────────────────────────────────────────

_oidc_discovery_cache: dict[str, Any] = {}


async def fetch_oidc_discovery(discovery_url: str) -> dict[str, Any]:
    """Fetch (and cache in-process) the OIDC discovery document."""
    if discovery_url in _oidc_discovery_cache:
        logger.debug("OIDC discovery cache hit for %s", discovery_url)
        cached: dict[str, Any] = _oidc_discovery_cache[discovery_url]
        return cached
    logger.info("Fetching OIDC discovery document from %s", discovery_url)
    async with httpx.AsyncClient() as client:
        resp = await client.get(discovery_url)
        resp.raise_for_status()
        doc: dict[str, Any] = resp.json()
    _oidc_discovery_cache[discovery_url] = doc
    logger.debug("OIDC discovery document cached for %s", discovery_url)
    return doc


async def exchange_oidc_code(
    token_endpoint: str, code: str, redirect_uri: str
) -> dict[str, Any]:
    """Exchange an authorization code for tokens at *token_endpoint*."""
    logger.info("Exchanging OIDC authorization code at %s", token_endpoint)
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            token_endpoint,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": settings.oidc_client_id,
                "client_secret": settings.oidc_client_secret,
            },
        )
        resp.raise_for_status()
        result: dict[str, Any] = resp.json()
    logger.debug("OIDC code exchange succeeded")
    return result


async def fetch_oidc_userinfo(
    userinfo_endpoint: str, access_token: str
) -> dict[str, Any]:
    """Fetch userinfo from the IdP using *access_token*."""
    logger.debug("Fetching OIDC userinfo from %s", userinfo_endpoint)
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            userinfo_endpoint,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        result: dict[str, Any] = resp.json()
    return result


# ── Role resolution ───────────────────────────────────────────────────────────


def resolve_role(idp_roles: list[str]) -> str:
    """Map a list of IdP role strings to the internal role.

    Returns ``"admin"`` if ``"admin"`` appears in *idp_roles* (case-insensitive),
    otherwise returns ``"user"``.
    """
    normalised = {r.lower() for r in idp_roles}
    return "admin" if "admin" in normalised else "user"


def extract_oidc_roles(userinfo: dict[str, Any]) -> list[str]:
    """Extract roles from an OIDC userinfo dict using the configured claim."""
    raw = userinfo.get(settings.oidc_roles_claim, [])
    if isinstance(raw, list):
        return [str(r) for r in raw]
    return []


def extract_saml_roles(attributes: dict[str, Any]) -> list[str]:
    """Extract roles from a SAML attribute dict using the configured attribute."""
    raw = attributes.get(settings.saml_roles_attribute, [])
    if isinstance(raw, list):
        return [str(r) for r in raw]
    return []


# ── User persistence ──────────────────────────────────────────────────────────


async def upsert_user(
    db: AsyncSession,
    *,
    sub: str,
    provider: str,
    email: str | None,
    display_name: str | None,
    role: str = "user",
) -> User:
    """Create or update a user record, syncing mutable fields on every login."""
    result = await db.execute(select(User).where(User.sub == sub))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            sub=sub,
            provider=provider,
            email=email,
            display_name=display_name,
            role=role,
        )
        db.add(user)
        logger.info(
            "New user created — provider: %s, email: %s, role: %s",
            provider, email, role,
        )
    else:
        user.email = email
        user.display_name = display_name
        # Role is always re-synced from the IdP on each login.
        user.role = role
        user.updated_at = datetime.now(UTC)
        logger.info(
            "Existing user updated — provider: %s, email: %s, role: %s",
            provider, email, role,
        )

    await db.commit()
    await db.refresh(user)
    return user
