"""Unit tests for auth route handlers."""

import json
from unittest.mock import MagicMock, mock_open, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from song_shake.api import app

client = TestClient(app)


# --- logout tests ---


class TestLogout:
    """Tests for GET /auth/logout."""

    @patch("song_shake.features.auth.routes.os.remove")
    @patch("song_shake.features.auth.routes.os.path.exists")
    def test_removes_oauth_file(self, mock_exists, mock_remove):
        """Should remove oauth.json when it exists."""
        mock_exists.return_value = True

        response = client.get("/auth/logout")

        assert response.status_code == 200
        assert response.json()["status"] == "logged_out"
        mock_remove.assert_called_once_with("oauth.json")

    @patch("song_shake.features.auth.routes.os.path.exists")
    def test_handles_missing_file(self, mock_exists):
        """Should succeed even when oauth.json doesn't exist."""
        mock_exists.return_value = False

        response = client.get("/auth/logout")

        assert response.status_code == 200
        assert response.json()["status"] == "logged_out"


# --- auth_status tests ---


class TestAuthStatus:
    """Tests for GET /auth/status."""

    @patch("song_shake.features.auth.routes._is_token_valid")
    def test_returns_authenticated_when_valid(self, mock_valid):
        """Should return authenticated=True when token is valid."""
        mock_valid.return_value = True

        response = client.get("/auth/status")

        assert response.status_code == 200
        assert response.json()["authenticated"] is True

    @patch("song_shake.features.auth.routes._is_token_valid")
    def test_returns_not_authenticated_when_invalid(self, mock_valid):
        """Should return authenticated=False when token is invalid."""
        mock_valid.return_value = False

        response = client.get("/auth/status")

        assert response.status_code == 200
        assert response.json()["authenticated"] is False


# --- _is_token_valid tests ---


class TestIsTokenValid:
    """Tests for _is_token_valid() helper."""

    @patch("song_shake.features.auth.routes.os.path.exists")
    def test_returns_false_when_no_file(self, mock_exists):
        """Should return False when oauth.json doesn't exist."""
        mock_exists.return_value = False

        from song_shake.features.auth.routes import _is_token_valid

        assert _is_token_valid() is False

    @patch("builtins.open", mock_open(read_data='{"access_token": "tok", "expires_at": 9999999999}'))
    @patch("song_shake.features.auth.routes.os.path.exists")
    def test_returns_true_for_valid_token(self, mock_exists):
        """Should return True when token exists and is not expired."""
        mock_exists.return_value = True

        from song_shake.features.auth.routes import _is_token_valid

        assert _is_token_valid() is True

    @patch("builtins.open", mock_open(read_data='{"access_token": "tok", "expires_at": 1}'))
    @patch("song_shake.features.auth.routes.os.path.exists")
    def test_returns_false_for_expired_token(self, mock_exists):
        """Should return False when token is expired."""
        mock_exists.return_value = True

        from song_shake.features.auth.routes import _is_token_valid

        assert _is_token_valid() is False

    @patch("builtins.open", mock_open(read_data="invalid json"))
    @patch("song_shake.features.auth.routes.os.path.exists")
    def test_returns_false_for_corrupt_file(self, mock_exists):
        """Should return False when file contains invalid JSON."""
        mock_exists.return_value = True

        from song_shake.features.auth.routes import _is_token_valid

        assert _is_token_valid() is False


# --- get_current_user tests ---


class TestGetCurrentUser:
    """Tests for GET /auth/me."""

    @patch("song_shake.features.auth.routes.os.path.exists")
    def test_returns_401_when_no_oauth_file(self, mock_exists):
        """Should return 401 when oauth.json doesn't exist."""
        mock_exists.return_value = False

        response = client.get("/auth/me")

        assert response.status_code == 401

    @patch("song_shake.features.auth.routes.requests.get")
    @patch(
        "builtins.open",
        mock_open(read_data='{"access_token": "test-token"}'),
    )
    @patch("song_shake.features.auth.routes.os.path.exists")
    def test_returns_user_from_channel_info(self, mock_exists, mock_get):
        """Should return user info from YouTube Channel API."""
        mock_exists.return_value = True

        channel_response = MagicMock()
        channel_response.status_code = 200
        channel_response.json.return_value = {
            "items": [
                {
                    "id": "UC123",
                    "snippet": {
                        "title": "Test User",
                        "thumbnails": {"default": {"url": "https://img.com/pic.jpg"}},
                    },
                }
            ]
        }
        mock_get.return_value = channel_response

        response = client.get("/auth/me")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "UC123"
        assert data["name"] == "Test User"
        assert data["authenticated"] is True

    @patch("song_shake.features.auth.routes.requests.get")
    @patch(
        "builtins.open",
        mock_open(read_data='{"access_token": "test-token"}'),
    )
    @patch("song_shake.features.auth.routes.os.path.exists")
    def test_falls_back_to_userinfo(self, mock_exists, mock_get):
        """Should fall back to userinfo endpoint when channel API returns no items."""
        mock_exists.return_value = True

        channel_response = MagicMock()
        channel_response.status_code = 200
        channel_response.json.return_value = {"items": []}

        userinfo_response = MagicMock()
        userinfo_response.status_code = 200
        userinfo_response.json.return_value = {
            "id": "user@example.com",
            "name": "Email User",
            "picture": "https://img.com/email.jpg",
        }

        mock_get.side_effect = [channel_response, userinfo_response]

        response = client.get("/auth/me")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Email User"
        assert data["authenticated"] is True

    @patch(
        "builtins.open",
        mock_open(read_data='{}'),
    )
    @patch("song_shake.features.auth.routes.os.path.exists")
    def test_returns_401_when_no_access_token(self, mock_exists):
        """Should return 401 when access_token is missing from file."""
        mock_exists.return_value = True

        response = client.get("/auth/me")

        assert response.status_code == 401


# --- login tests ---


class TestLogin:
    """Tests for POST /auth/login."""

    def test_returns_400_when_no_headers(self):
        """Should return 400 when headers_raw is empty."""
        response = client.post("/auth/login", json={})

        assert response.status_code == 400
        assert "Headers required" in response.json()["detail"]

    @patch("song_shake.features.auth.routes.YTMusic")
    @patch("builtins.open", mock_open())
    def test_login_with_json_headers(self, mock_ytmusic):
        """Should write JSON headers directly to oauth.json."""
        mock_ytmusic.return_value = MagicMock()
        json_headers = json.dumps({"access_token": "tok", "refresh_token": "ref"})

        response = client.post("/auth/login", json={"headers_raw": json_headers})

        assert response.status_code == 200
        assert response.json()["status"] == "success"

    @patch("song_shake.features.auth.routes.os.path.exists")
    @patch("song_shake.features.auth.routes.os.remove")
    @patch("song_shake.features.auth.routes.YTMusic")
    def test_login_cleans_up_on_failure(self, mock_ytmusic, mock_remove, mock_exists):
        """Should remove oauth.json when login fails."""
        mock_ytmusic.side_effect = Exception("Invalid format")
        mock_exists.return_value = True

        response = client.post(
            "/auth/login", json={"headers_raw": "invalid-data"}
        )

        assert response.status_code == 400
        assert "Invalid headers format" in response.json()["detail"]


# --- auth_config tests ---


class TestAuthConfig:
    """Tests for GET /auth/config."""

    @patch("song_shake.features.auth.routes.os.getenv")
    def test_returns_use_env_true_when_set(self, mock_getenv):
        """Should return use_env=True when both env vars are set."""
        mock_getenv.side_effect = lambda k: {
            "GOOGLE_CLIENT_ID": "id",
            "GOOGLE_CLIENT_SECRET": "secret",
        }.get(k)

        response = client.get("/auth/config")

        assert response.status_code == 200
        assert response.json()["use_env"] is True

    @patch("song_shake.features.auth.routes.os.getenv")
    def test_returns_use_env_false_when_missing(self, mock_getenv):
        """Should return use_env=False when env vars are not set."""
        mock_getenv.return_value = None

        response = client.get("/auth/config")

        assert response.status_code == 200
        assert response.json()["use_env"] is False


# --- google_auth_login tests ---


class TestGoogleAuthLogin:
    """Tests for GET /auth/google/login."""

    @patch("song_shake.features.auth.routes.os.getenv")
    def test_redirects_to_google(self, mock_getenv):
        """Should redirect to Google OAuth with correct params."""
        mock_getenv.side_effect = lambda k, *args: {
            "GOOGLE_CLIENT_ID": "test-client-id",
            "OAUTH_REDIRECT_URI": "http://localhost:8000/auth/google/callback",
        }.get(k, args[0] if args else None)

        response = client.get("/auth/google/login", follow_redirects=False)

        assert response.status_code == 307
        location = response.headers["location"]
        assert "accounts.google.com" in location
        assert "test-client-id" in location

    @patch("song_shake.features.auth.routes.os.getenv")
    def test_returns_400_without_client_id(self, mock_getenv):
        """Should return 400 when GOOGLE_CLIENT_ID is not set."""
        mock_getenv.return_value = None

        response = client.get("/auth/google/login")

        assert response.status_code == 400


# --- google_auth_callback tests ---


class TestGoogleAuthCallback:
    """Tests for GET /auth/google/callback."""

    @patch("builtins.open", mock_open())
    @patch("song_shake.features.auth.routes.requests.post")
    @patch("song_shake.features.auth.routes.os.getenv")
    def test_exchanges_code_for_token(self, mock_getenv, mock_post):
        """Should exchange auth code for tokens and redirect to frontend."""
        mock_getenv.side_effect = lambda k, *args: {
            "GOOGLE_CLIENT_ID": "client-id",
            "GOOGLE_CLIENT_SECRET": "client-secret",
            "OAUTH_REDIRECT_URI": "http://localhost:8000/auth/google/callback",
            "FRONTEND_URL": "http://localhost:5173/",
        }.get(k, args[0] if args else None)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new-token",
            "refresh_token": "new-refresh",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        response = client.get(
            "/auth/google/callback?code=auth-code-123", follow_redirects=False
        )

        assert response.status_code == 307
        assert response.headers["location"] == "http://localhost:5173/"

    @patch("song_shake.features.auth.routes.os.getenv")
    def test_returns_400_without_credentials(self, mock_getenv):
        """Should return 400 when client credentials are missing."""
        mock_getenv.return_value = None

        response = client.get("/auth/google/callback?code=test")

        assert response.status_code == 400

    @patch("song_shake.features.auth.routes.requests.post")
    @patch("song_shake.features.auth.routes.os.getenv")
    def test_returns_400_on_token_exchange_failure(self, mock_getenv, mock_post):
        """Should return 400 when token exchange fails."""
        mock_getenv.side_effect = lambda k, *args: {
            "GOOGLE_CLIENT_ID": "id",
            "GOOGLE_CLIENT_SECRET": "secret",
            "OAUTH_REDIRECT_URI": "http://localhost:8000/auth/google/callback",
            "FRONTEND_URL": "http://localhost:5173/",
        }.get(k, args[0] if args else None)

        import requests as req

        mock_post.side_effect = req.RequestException("Network error")

        response = client.get("/auth/google/callback?code=bad-code")

        assert response.status_code == 400


# --- google_auth_init tests ---


class TestGoogleAuthInit:
    """Tests for POST /auth/google/init."""

    @patch("song_shake.features.auth.routes.OAuthCredentials")
    @patch("song_shake.features.auth.routes.os.getenv")
    def test_returns_device_code(self, mock_getenv, mock_creds_cls):
        """Should return device code from OAuthCredentials."""
        mock_getenv.return_value = None
        mock_creds = MagicMock()
        mock_creds.get_code.return_value = {
            "device_code": "dev123",
            "user_code": "USR-123",
            "verification_url": "https://example.com",
        }
        mock_creds_cls.return_value = mock_creds

        response = client.post(
            "/auth/google/init",
            json={"client_id": "test-id", "client_secret": "test-secret"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["device_code"] == "dev123"

    @patch("song_shake.features.auth.routes.os.getenv")
    def test_returns_400_without_credentials(self, mock_getenv):
        """Should return 400 when no credentials available."""
        mock_getenv.return_value = None

        response = client.post("/auth/google/init", json={})

        assert response.status_code == 400


# --- google_auth_poll tests ---


class TestGoogleAuthPoll:
    """Tests for POST /auth/google/poll."""

    @patch("builtins.open", mock_open())
    @patch("song_shake.features.auth.routes.RefreshingToken")
    @patch("song_shake.features.auth.routes.OAuthCredentials")
    @patch("song_shake.features.auth.routes.os.getenv")
    def test_returns_success_on_valid_token(
        self, mock_getenv, mock_creds_cls, mock_refresh_cls
    ):
        """Should return success and save token when poll succeeds."""
        mock_getenv.return_value = None
        mock_creds = MagicMock()
        mock_creds.token_from_code.return_value = {
            "access_token": "tok",
            "refresh_token": "ref",
        }
        mock_creds_cls.return_value = mock_creds

        mock_ref_token = MagicMock()
        mock_ref_token.as_json.return_value = '{"access_token": "tok"}'
        mock_refresh_cls.return_value = mock_ref_token

        response = client.post(
            "/auth/google/poll",
            json={
                "device_code": "dev123",
                "client_id": "test-id",
                "client_secret": "test-secret",
            },
        )

        assert response.status_code == 200
        assert response.json()["status"] == "success"

    @patch("song_shake.features.auth.routes.OAuthCredentials")
    @patch("song_shake.features.auth.routes.os.getenv")
    def test_returns_pending_when_authorization_pending(
        self, mock_getenv, mock_creds_cls
    ):
        """Should return pending status when user hasn't authorized yet."""
        mock_getenv.return_value = None
        mock_creds = MagicMock()
        mock_creds.token_from_code.side_effect = Exception("authorization_pending")
        mock_creds_cls.return_value = mock_creds

        response = client.post(
            "/auth/google/poll",
            json={
                "device_code": "dev123",
                "client_id": "test-id",
                "client_secret": "test-secret",
            },
        )

        assert response.status_code == 200
        assert response.json()["status"] == "pending"

    @patch("song_shake.features.auth.routes.os.getenv")
    def test_returns_400_without_credentials(self, mock_getenv):
        """Should return 400 when credentials are missing."""
        mock_getenv.return_value = None

        response = client.post(
            "/auth/google/poll", json={"device_code": "dev123"}
        )

        assert response.status_code == 400

    @patch("song_shake.features.auth.routes.OAuthCredentials")
    @patch("song_shake.features.auth.routes.os.getenv")
    def test_returns_400_on_unexpected_error(self, mock_getenv, mock_creds_cls):
        """Should return 400 when an unexpected error occurs."""
        mock_getenv.return_value = None
        mock_creds = MagicMock()
        mock_creds.token_from_code.side_effect = Exception("Something went wrong")
        mock_creds_cls.return_value = mock_creds

        response = client.post(
            "/auth/google/poll",
            json={
                "device_code": "dev123",
                "client_id": "test-id",
                "client_secret": "test-secret",
            },
        )

        assert response.status_code == 400
