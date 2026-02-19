"""Authentication routes for Song Shake API.

Handles Google OAuth login flow, JWT-based session management, and user
profile lookup. Google OAuth tokens are stored per-user in TinyDB; the app
issues its own JWT for session management.
"""

import os
import time

import requests
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import RedirectResponse
from urllib.parse import urlencode

from song_shake.features.auth import jwt as app_jwt
from song_shake.features.auth import token_store
from song_shake.features.auth.dependencies import get_current_user
from song_shake.platform.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


# --- Helpers ---


def _fetch_google_user_profile(access_token: str) -> dict:
    """Fetch user profile from Google APIs.

    Tries YouTube Channel API first (for channel ID + name), then falls back
    to Google UserInfo endpoint.

    Returns:
        Dict with keys: ``id``, ``name``, ``thumbnail``.

    Raises:
        ValueError: If no profile could be fetched.
    """
    headers = {"Authorization": f"Bearer {access_token}"}

    # 1. Try YouTube Channel info (best for stable user ID)
    try:
        res = requests.get(
            "https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true",
            headers=headers,
            timeout=10,
        )
        if res.status_code == 200:
            data = res.json()
            if data.get("items"):
                item = data["items"][0]
                snippet = item["snippet"]
                return {
                    "id": item["id"],
                    "name": snippet.get("title", "YouTube User"),
                    "thumbnail": snippet.get("thumbnails", {}).get("default", {}).get("url"),
                }
    except requests.RequestException as exc:
        logger.debug("channel_api_failed", error=str(exc))

    # 2. Try Google UserInfo
    try:
        res = requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers=headers,
            timeout=10,
        )
        if res.status_code == 200:
            uinfo = res.json()
            return {
                "id": uinfo.get("id") or uinfo.get("email"),
                "name": uinfo.get("name") or uinfo.get("email") or "User",
                "thumbnail": uinfo.get("picture"),
            }
    except requests.RequestException as exc:
        logger.debug("userinfo_api_failed", error=str(exc))

    raise ValueError("Could not fetch user profile from Google")


# --- Routes ---


@router.get("/google/login")
def google_auth_login():
    """Redirect the user to Google's OAuth consent screen."""
    logger.info("google_auth_login_started")
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    if not client_id:
        raise HTTPException(status_code=400, detail="GOOGLE_CLIENT_ID not set in .env")

    redirect_uri = os.getenv("OAUTH_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
    scope = "https://www.googleapis.com/auth/youtube"

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scope,
        "access_type": "offline",
        "prompt": "consent",
    }
    url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return RedirectResponse(url)


@router.get("/google/callback")
def google_auth_callback(code: str):
    """Exchange authorization code for tokens, store per-user, issue JWT."""
    logger.info("google_auth_callback_started")
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_uri = os.getenv("OAUTH_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")

    if not client_id or not client_secret:
        raise HTTPException(status_code=400, detail="Credentials not set in .env")

    # Exchange code for tokens
    try:
        response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
            timeout=10,
        )
        response.raise_for_status()
        tokens = response.json()
    except requests.RequestException as exc:
        logger.error("google_token_exchange_failed", error=str(exc))
        raise HTTPException(status_code=400, detail="Token exchange failed")

    tokens["expires_at"] = int(time.time()) + tokens.get("expires_in", 3600)

    # Fetch user profile from Google
    access_token = tokens["access_token"]
    try:
        profile = _fetch_google_user_profile(access_token)
    except ValueError:
        logger.error("google_profile_fetch_failed")
        raise HTTPException(status_code=400, detail="Could not identify user from Google")

    user_id = profile["id"]
    user_name = profile["name"]
    user_thumb = profile.get("thumbnail")

    # Store Google tokens per-user in TinyDB
    token_store.save_google_tokens(user_id, tokens)

    # Issue app JWT
    jwt_token = app_jwt.create_access_token(
        user_id=user_id,
        name=user_name,
        thumbnail=user_thumb,
    )

    logger.info("google_auth_callback_success", user_id=user_id)

    # Redirect to frontend with JWT in query param
    return RedirectResponse(f"{frontend_url}/login?token={jwt_token}")


@router.get("/me")
def get_current_user_profile(user: dict = Depends(get_current_user)):
    """Return the current user's profile from their JWT claims."""
    logger.info("get_current_user_started", user_id=user["sub"])
    return {
        "id": user["sub"],
        "name": user["name"],
        "thumbnail": user.get("thumb"),
        "authenticated": True,
    }


@router.get("/status")
def auth_status(authorization: str = Header(default="")):
    """Check if the caller has a valid JWT.

    Unlike other endpoints, this does NOT raise 401 on missing/invalid tokens.
    Instead, it returns ``{authenticated: false}`` so the frontend can check
    auth state without triggering error interceptors.
    """
    if not authorization.startswith("Bearer "):
        return {"authenticated": False}

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        return {"authenticated": False}

    try:
        payload = app_jwt.decode_access_token(token)
        return {
            "authenticated": True,
            "user": {
                "id": payload["sub"],
                "name": payload["name"],
                "thumbnail": payload.get("thumb"),
            },
        }
    except ValueError:
        return {"authenticated": False}


@router.get("/refresh")
def refresh_auth(user: dict = Depends(get_current_user)):
    """Refresh the Google token and issue a new app JWT.

    The frontend should call this when it gets a 401 or proactively before
    the JWT expires.
    """
    logger.info("refresh_auth_started", user_id=user["sub"])
    user_id = user["sub"]

    tokens = token_store.get_google_tokens(user_id)
    if not tokens:
        raise HTTPException(status_code=401, detail="No stored Google tokens")

    # Refresh Google token
    refresh_tok = tokens.get("refresh_token")
    if not refresh_tok:
        raise HTTPException(status_code=401, detail="No refresh token available")

    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise HTTPException(status_code=401, detail="Missing OAuth credentials")

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
    except requests.RequestException as exc:
        logger.warning("google_token_refresh_failed", user_id=user_id, error=str(exc))
        raise HTTPException(status_code=401, detail="Token refresh failed")

    tokens["access_token"] = new_tokens["access_token"]
    tokens["expires_in"] = new_tokens.get("expires_in", 3600)
    tokens["expires_at"] = int(time.time()) + tokens["expires_in"]
    if "refresh_token" in new_tokens:
        tokens["refresh_token"] = new_tokens["refresh_token"]

    token_store.save_google_tokens(user_id, tokens)

    # Issue fresh app JWT (may have updated name/thumbnail)
    new_jwt = app_jwt.create_access_token(
        user_id=user_id,
        name=user["name"],
        thumbnail=user.get("thumb"),
    )

    logger.info("refresh_auth_success", user_id=user_id)
    return {"refreshed": True, "token": new_jwt, "expires_at": tokens["expires_at"]}


@router.get("/logout")
def logout(user: dict = Depends(get_current_user)):
    """Delete the user's stored Google tokens."""
    logger.info("logout_started", user_id=user["sub"])
    token_store.delete_google_tokens(user["sub"])
    logger.info("logout_success", user_id=user["sub"])
    return {"status": "logged_out"}
