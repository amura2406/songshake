"""JWT utility module for creating and verifying app-level access tokens.

Separates app session management from Google OAuth tokens. The JWT identifies
which user is making a request; Google tokens are stored server-side and used
only to call YouTube APIs.
"""

import os
import time
from typing import Any

import jwt

from song_shake.platform.logging_config import get_logger

logger = get_logger(__name__)

# Algorithm used for signing — HS256 is symmetric (shared secret).
_ALGORITHM = "HS256"

# Token lifetime: 24 hours
_TOKEN_LIFETIME_SECONDS = 24 * 60 * 60


def _get_secret() -> str:
    """Return the JWT signing secret from environment.

    In development mode (ENV=development), auto-generates a secret if
    JWT_SECRET is not set. In production, missing JWT_SECRET is fatal.
    """
    secret = os.getenv("JWT_SECRET")
    if secret:
        return secret

    env = os.getenv("ENV", "development")
    if env == "development":
        # Deterministic dev secret — stable across restarts so tokens survive
        # server reloads during development.
        logger.warning(
            "jwt_secret_missing_using_dev_default",
            hint="Set JWT_SECRET in .env for production",
        )
        return "songshake-dev-secret-do-not-use-in-prod"

    raise RuntimeError(
        "JWT_SECRET environment variable is required in production. "
        "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
    )


def create_access_token(
    user_id: str,
    name: str,
    thumbnail: str | None = None,
) -> str:
    """Create a signed JWT for the given user.

    Args:
        user_id: Google user/channel ID (becomes the ``sub`` claim).
        name: Display name for the user.
        thumbnail: Optional profile picture URL.

    Returns:
        Encoded JWT string.
    """
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": user_id,
        "name": name,
        "thumb": thumbnail,
        "iat": now,
        "exp": now + _TOKEN_LIFETIME_SECONDS,
    }
    token = jwt.encode(payload, _get_secret(), algorithm=_ALGORITHM)
    logger.debug("jwt_created", user_id=user_id)
    return token


def decode_access_token(token: str) -> dict:
    """Verify and decode a JWT.

    Args:
        token: Encoded JWT string.

    Returns:
        Decoded payload dict containing ``sub``, ``name``, ``thumb``, etc.

    Raises:
        ValueError: If the token is invalid, expired, or has a bad signature.
    """
    try:
        payload = jwt.decode(token, _get_secret(), algorithms=[_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired")
    except jwt.InvalidTokenError as exc:
        raise ValueError(f"Invalid token: {exc}")
