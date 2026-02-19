"""Authentication routes for Song Shake API."""

import json
import os
import time

import requests
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from typing import Optional
from urllib.parse import urlencode

from song_shake.features.auth import auth
from song_shake.platform.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


# --- Helpers ---

OAUTH_FILE = "oauth.json"


def get_ytmusic():
    """Get an authenticated YTMusic instance or raise 401."""
    try:
        return auth.get_ytmusic()
    except Exception:
        raise HTTPException(status_code=401, detail="Authentication required")


def _is_token_valid() -> bool:
    """Check if oauth.json exists and the token is not expired."""
    if not os.path.exists(OAUTH_FILE):
        return False
    try:
        with open(OAUTH_FILE) as f:
            tokens = json.load(f)
        expires_at = tokens.get("expires_at")
        if expires_at and time.time() > expires_at:
            return False
        # Must have at least an access_token or refresh_token
        return bool(tokens.get("access_token") or tokens.get("refresh_token"))
    except (json.JSONDecodeError, OSError):
        return False


# --- Routes ---

@router.get("/logout")
def logout():
    logger.info("logout_started")
    if os.path.exists(OAUTH_FILE):
        os.remove(OAUTH_FILE)
    logger.info("logout_success")
    return {"status": "logged_out"}


@router.get("/me")
def get_current_user():
    logger.info("get_current_user_started")
    if not os.path.exists(OAUTH_FILE):
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        with open(OAUTH_FILE) as f:
            tokens = json.load(f)

        token = tokens.get("access_token")
        if not token:
            raise HTTPException(status_code=401, detail="No access token")

        headers = {"Authorization": f"Bearer {token}"}

        # 1. Try Channel Info (best for stable ID)
        res = requests.get(
            "https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true",
            headers=headers,
            timeout=10,
        )

        user_id = "web_user"
        name = "Authenticated User"
        thumb = None

        if res.status_code == 200:
            data = res.json()
            if data.get("items"):
                item = data["items"][0]
                user_id = item["id"]
                snippet = item["snippet"]
                name = snippet.get("title", "YouTube User")
                thumb = snippet["thumbnails"]["default"]["url"]
                logger.info("get_current_user_success", user_id=user_id)
                return {
                    "id": user_id,
                    "name": name,
                    "thumbnail": thumb,
                    "authenticated": True,
                }

        # 2. Try UserInfo for name/email (requires profile/email scope)
        try:
            res2 = requests.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers=headers,
                timeout=10,
            )
            if res2.status_code == 200:
                uinfo = res2.json()
                user_id = uinfo.get("id") or uinfo.get("email") or "web_user"
                name = uinfo.get("name") or uinfo.get("email") or "User"
                thumb = uinfo.get("picture")
                logger.info("get_current_user_success", user_id=user_id, source="userinfo")
                return {
                    "id": user_id,
                    "name": name,
                    "thumbnail": thumb,
                    "authenticated": True,
                }
        except requests.RequestException as e:
            logger.warning("userinfo_endpoint_failed", error=str(e))

        # 3. Fallback
        logger.info("get_current_user_success", user_id="web_user", source="fallback")
        return {
            "id": "web_user",
            "name": "Authenticated User (No Channel)",
            "thumbnail": None,
            "authenticated": True,
            "note": "Could not fetch channel profile",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_current_user_failed", error=str(e))
        return {"authenticated": False}


@router.get("/status")
def auth_status():
    authenticated = _is_token_valid()
    return {"authenticated": authenticated}


@router.get("/google/login")
def google_auth_login():
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
    logger.info("google_auth_callback_started")
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_uri = os.getenv("OAUTH_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173/")

    if not client_id or not client_secret:
        raise HTTPException(status_code=400, detail="Credentials not set in .env")

    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }

    try:
        response = requests.post(token_url, data=data, timeout=10)
        response.raise_for_status()
        tokens = response.json()

        tokens["expires_at"] = int(time.time()) + tokens.get("expires_in", 3600)

        with open(OAUTH_FILE, "w") as f:
            json.dump(tokens, f)

        logger.info("google_auth_callback_success")
        return RedirectResponse(frontend_url)
    except requests.RequestException as e:
        logger.error("google_auth_callback_failed", error=str(e))
        raise HTTPException(status_code=400, detail="Token exchange failed")

