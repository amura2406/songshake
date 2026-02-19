"""FastAPI dependency functions for authentication.

Provides injectable dependencies that extract user identity from JWT tokens
and build authenticated YTMusic instances using per-user Google tokens.
"""

import os
import time

import requests
from fastapi import Header, HTTPException
from ytmusicapi import YTMusic
from ytmusicapi.auth.oauth import OAuthCredentials

from song_shake.features.auth import jwt as app_jwt
from song_shake.features.auth import token_store
from song_shake.platform.logging_config import get_logger

logger = get_logger(__name__)


def get_current_user(
    authorization: str = Header(default=""),
    token: str | None = None,
) -> dict:
    """Extract and validate JWT from the Authorization header or query param.

    Supports two authentication methods:
    1. ``Authorization: Bearer <token>`` header (preferred, used by Axios)
    2. ``?token=<jwt>`` query param (fallback for EventSource/SSE which
       cannot set custom headers)

    Usage::

        @router.get("/protected")
        def endpoint(user: dict = Depends(get_current_user)):
            user_id = user["sub"]

    Returns:
        Decoded JWT payload with keys: ``sub``, ``name``, ``thumb``, etc.

    Raises:
        HTTPException(401): If the token is missing, invalid, or expired.
    """
    jwt_token = None

    # Try Authorization header first
    if authorization.startswith("Bearer "):
        jwt_token = authorization.removeprefix("Bearer ").strip()

    # Fall back to query param (for SSE endpoints)
    if not jwt_token and token:
        jwt_token = token

    if not jwt_token:
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid Authorization header",
        )

    try:
        payload = app_jwt.decode_access_token(jwt_token)
        return payload
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))


def _refresh_google_token(user_id: str, tokens: dict) -> dict | None:
    """Refresh a user's Google access token using their refresh_token.

    Returns updated token dict on success, None on failure.
    Saves refreshed tokens back to the store.
    """
    refresh_tok = tokens.get("refresh_token")
    if not refresh_tok:
        return None

    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    if not client_id or not client_secret:
        logger.warning("google_refresh_skipped_no_credentials")
        return None

    try:
        resp = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_tok,
                "grant_type": "refresh_token",
            },
            timeout=10,
        )
        resp.raise_for_status()
        new_tokens = resp.json()

        tokens["access_token"] = new_tokens["access_token"]
        tokens["expires_in"] = new_tokens.get("expires_in", 3600)
        tokens["expires_at"] = int(time.time()) + tokens["expires_in"]
        if "refresh_token" in new_tokens:
            tokens["refresh_token"] = new_tokens["refresh_token"]

        token_store.save_google_tokens(user_id, tokens)
        logger.info("google_token_refreshed", user_id=user_id)
        return tokens
    except requests.RequestException as exc:
        logger.warning("google_token_refresh_failed", user_id=user_id, error=str(exc))
        return None


def get_authenticated_ytmusic(user: dict) -> YTMusic:
    """Build an authenticated YTMusic instance for the current user.

    Loads the user's Google OAuth tokens from the token store, refreshes
    them if expired, and constructs a YTMusic client.

    This is NOT a FastAPI ``Depends()`` function itself — call it explicitly
    from route handlers that need YTMusic access::

        @router.get("/playlists")
        def get_playlists(user: dict = Depends(get_current_user)):
            yt = get_authenticated_ytmusic(user)

    Raises:
        HTTPException(401): If no Google tokens exist for this user or
            tokens cannot be refreshed.
    """
    user_id = user["sub"]
    tokens = token_store.get_google_tokens(user_id)

    if not tokens:
        raise HTTPException(
            status_code=401,
            detail="No Google tokens found. Please re-authenticate with Google.",
        )

    # Check if Google token needs refresh
    expires_at = tokens.get("expires_at", 0)
    if time.time() >= expires_at:
        refreshed = _refresh_google_token(user_id, tokens)
        if not refreshed:
            raise HTTPException(
                status_code=401,
                detail="Google token expired and refresh failed. Please re-authenticate.",
            )
        tokens = refreshed

    # Build YTMusic client from stored tokens
    creds = None
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    if client_id and client_secret:
        creds = OAuthCredentials(client_id=client_id, client_secret=client_secret)

    valid_keys = {"scope", "token_type", "access_token", "refresh_token", "expires_at", "expires_in"}
    clean_auth = {k: v for k, v in tokens.items() if k in valid_keys}

    return YTMusic(auth=clean_auth, oauth_credentials=creds)
