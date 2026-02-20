"""Unit tests for auth route handlers (JWT-based)."""

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from song_shake.api import app
from song_shake.features.auth import jwt as app_jwt
from song_shake.features.auth.dependencies import get_current_user
from song_shake.platform.storage_factory import get_token_storage

client = TestClient(app)

FAKE_USER = {"sub": "test_user_123", "name": "Test User", "thumb": None}


@pytest.fixture(autouse=True)
def _cleanup():
    """Clear dependency overrides after each test."""
    yield
    app.dependency_overrides.clear()


def _make_jwt(claims=None):
    """Create a valid JWT for testing."""
    payload = claims or FAKE_USER
    return app_jwt.create_access_token(
        user_id=payload["sub"],
        name=payload.get("name", "Test"),
        thumbnail=payload.get("thumb"),
    )


def _make_mock_token_storage(tokens=None):
    """Create a mock TokenStoragePort."""
    mock = MagicMock()
    mock.get_google_tokens.return_value = tokens
    return mock


# --- auth/me tests ---


class TestAuthMe:
    """Tests for GET /auth/me."""

    def test_returns_user_profile_with_valid_jwt(self):
        """Should return user profile from JWT claims."""
        token = _make_jwt()
        response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "test_user_123"
        assert data["name"] == "Test User"
        assert data["authenticated"] is True

    def test_returns_401_without_token(self):
        """Should return 401 when no token is provided."""
        response = client.get("/auth/me")
        assert response.status_code == 401

    def test_returns_401_with_invalid_token(self):
        """Should return 401 when token is invalid."""
        response = client.get("/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
        assert response.status_code == 401

    def test_returns_401_with_expired_token(self):
        """Should return 401 when token has expired."""
        import jwt
        import time

        token = jwt.encode(
            {"sub": "user", "name": "Test", "exp": int(time.time()) - 3600},
            app_jwt._get_secret(),
            algorithm="HS256",
        )
        response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401


# --- auth/status tests ---


class TestAuthStatus:
    """Tests for GET /auth/status."""

    def test_returns_authenticated_with_valid_jwt(self):
        """Should return authenticated=True with valid JWT."""
        token = _make_jwt()
        response = client.get("/auth/status", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200
        assert response.json()["authenticated"] is True

    def test_returns_not_authenticated_without_token(self):
        """Should return authenticated=False without JWT (no 401)."""
        response = client.get("/auth/status")

        assert response.status_code == 200
        assert response.json()["authenticated"] is False

    def test_returns_not_authenticated_with_bad_token(self):
        """Should return authenticated=False with invalid JWT."""
        response = client.get("/auth/status", headers={"Authorization": "Bearer bad.token"})

        assert response.status_code == 200
        assert response.json()["authenticated"] is False


# --- auth/logout tests ---


class TestLogout:
    """Tests for GET /auth/logout."""

    def test_logout_clears_tokens(self):
        """Should delete stored Google tokens for the user."""
        mock_ts = _make_mock_token_storage()
        app.dependency_overrides[get_token_storage] = lambda: mock_ts

        token = _make_jwt()
        response = client.get("/auth/logout", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200
        assert response.json()["status"] == "logged_out"
        mock_ts.delete_google_tokens.assert_called_once_with("test_user_123")

    def test_logout_requires_auth(self):
        """Should return 401 when not authenticated."""
        response = client.get("/auth/logout")
        assert response.status_code == 401


# --- auth/refresh tests ---


class TestRefresh:
    """Tests for GET /auth/refresh."""

    @patch("song_shake.features.auth.routes.requests.post")
    def test_refresh_issues_new_jwt(self, mock_post):
        """Should refresh Google tokens and issue a new JWT."""
        mock_ts = _make_mock_token_storage({
            "access_token": "old_token",
            "refresh_token": "valid_refresh",
        })
        app.dependency_overrides[get_token_storage] = lambda: mock_ts

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "access_token": "new_access",
            "expires_in": 3600,
        }
        mock_post.return_value = mock_resp

        token = _make_jwt()
        with patch.dict(os.environ, {"GOOGLE_CLIENT_ID": "cid", "GOOGLE_CLIENT_SECRET": "csec"}):
            response = client.get("/auth/refresh", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["refreshed"] is True

    def test_refresh_fails_without_stored_tokens(self):
        """Should return 401 when no stored tokens found."""
        mock_ts = _make_mock_token_storage(None)
        app.dependency_overrides[get_token_storage] = lambda: mock_ts

        token = _make_jwt()
        response = client.get("/auth/refresh", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 401

    def test_refresh_requires_auth(self):
        """Should return 401 when not authenticated."""
        response = client.get("/auth/refresh")
        assert response.status_code == 401


# --- Token query param support (for SSE) ---


class TestTokenQueryParam:
    """Tests for query param JWT support (SSE compatibility)."""

    def test_accepts_token_via_query_param(self):
        """Should authenticate using ?token= query param."""
        app.dependency_overrides.clear()
        token = _make_jwt()
        # Use a protected endpoint that uses get_current_user
        response = client.get(f"/auth/me?token={token}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "test_user_123"

    def test_header_takes_precedence_over_query_param(self):
        """Should prefer Authorization header over query param."""
        app.dependency_overrides.clear()
        token = _make_jwt()
        response = client.get(
            f"/auth/me?token=invalid.token",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "test_user_123"
