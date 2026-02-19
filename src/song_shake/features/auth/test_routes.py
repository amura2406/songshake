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




