"""Unit tests for playlist route handlers."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from song_shake.api import app
from song_shake.features.auth.dependencies import get_current_user

client = TestClient(app)


# --- Sample data ---

SAMPLE_PLAYLISTS = [
    {
        "playlistId": "PL_abc",
        "title": "My Playlist",
        "thumbnails": [{"url": "https://example.com/thumb.jpg", "width": 226, "height": 226}],
        "count": 10,
        "description": "Test playlist",
    },
    {
        "playlistId": "PL_def",
        "title": "Another Playlist",
        "thumbnails": [{"url": "https://example.com/thumb2.jpg", "width": 226, "height": 226}],
        "count": 5,
    },
]

FAKE_USER = {"sub": "test_user_123", "name": "Test User", "thumb": None}


def _mock_ytmusic(playlists=None):
    """Create a mock YTMusic instance."""
    yt = MagicMock()
    yt.get_library_playlists.return_value = playlists if playlists is not None else list(SAMPLE_PLAYLISTS)
    return yt


@pytest.fixture(autouse=True)
def _override_auth_and_cleanup():
    """Override auth dependency and reset after each test."""
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    yield
    app.dependency_overrides.clear()


# --- get_playlists tests ---


class TestGetPlaylists:
    """Tests for GET /playlists."""

    @patch("song_shake.features.songs.routes_playlists.token_store.get_google_tokens")
    @patch("song_shake.features.songs.routes_playlists.get_authenticated_ytmusic")
    @patch("song_shake.features.songs.routes_playlists.auth.get_data_api_playlists")
    @patch("song_shake.features.songs.routes_playlists.job_storage.get_all_active_jobs")
    @patch("song_shake.features.songs.routes_playlists.storage.get_all_history")
    def test_returns_playlists_with_liked_music(self, mock_history, mock_tasks, mock_data_api, mock_get_yt, mock_tokens):
        """Should return playlists with Liked Music prepended when not present."""
        mock_get_yt.return_value = _mock_ytmusic()
        mock_tokens.return_value = {"access_token": "fake_token"}
        mock_data_api.return_value = list(SAMPLE_PLAYLISTS)
        mock_history.return_value = {}
        mock_tasks.return_value = {}

        response = client.get("/playlists")

        assert response.status_code == 200
        data = response.json()
        # Liked Music should be inserted at index 0
        assert data[0]["playlistId"] == "LM"
        assert data[0]["title"] == "Liked Music"
        # Original 2 playlists + Liked Music = 3
        assert len(data) == 3

    @patch("song_shake.features.songs.routes_playlists.token_store.get_google_tokens")
    @patch("song_shake.features.songs.routes_playlists.get_authenticated_ytmusic")
    @patch("song_shake.features.songs.routes_playlists.auth.get_data_api_playlists")
    @patch("song_shake.features.songs.routes_playlists.job_storage.get_all_active_jobs")
    @patch("song_shake.features.songs.routes_playlists.storage.get_all_history")
    def test_does_not_duplicate_liked_music(self, mock_history, mock_tasks, mock_data_api, mock_get_yt, mock_tokens):
        """Should not add Liked Music if already present."""
        playlists_with_liked = [
            {"playlistId": "LM", "title": "Your Likes", "thumbnails": [], "count": 50}
        ] + list(SAMPLE_PLAYLISTS)
        mock_get_yt.return_value = _mock_ytmusic(playlists_with_liked)
        mock_tokens.return_value = {"access_token": "fake_token"}
        mock_data_api.return_value = playlists_with_liked
        mock_history.return_value = {}
        mock_tasks.return_value = {}

        response = client.get("/playlists")

        data = response.json()
        liked_count = sum(1 for p in data if p["playlistId"] == "LM")
        assert liked_count == 1

    @patch("song_shake.features.songs.routes_playlists.token_store.get_google_tokens")
    @patch("song_shake.features.songs.routes_playlists.get_authenticated_ytmusic")
    @patch("song_shake.features.songs.routes_playlists.auth.get_data_api_playlists")
    @patch("song_shake.features.songs.routes_playlists.job_storage.get_all_active_jobs")
    @patch("song_shake.features.songs.routes_playlists.storage.get_all_history")
    def test_merges_enrichment_history(self, mock_history, mock_tasks, mock_data_api, mock_get_yt, mock_tokens):
        """Should merge enrichment history into playlist responses."""
        mock_get_yt.return_value = _mock_ytmusic()
        mock_tokens.return_value = {"access_token": "fake_token"}
        mock_data_api.return_value = list(SAMPLE_PLAYLISTS)
        mock_history.return_value = {
            "PL_abc": {
                "last_processed": "2026-01-15T10:00:00",
                "status": "completed",
            }
        }
        mock_tasks.return_value = {}

        response = client.get("/playlists")

        data = response.json()
        pl_abc = next(p for p in data if p["playlistId"] == "PL_abc")
        assert pl_abc["last_processed"] == "2026-01-15T10:00:00"
        assert pl_abc["last_status"] == "completed"

    @patch("song_shake.features.songs.routes_playlists.token_store.get_google_tokens")
    @patch("song_shake.features.songs.routes_playlists.get_authenticated_ytmusic")
    @patch("song_shake.features.songs.routes_playlists.auth.get_data_api_playlists")
    @patch("song_shake.features.songs.routes_playlists.job_storage.get_all_active_jobs")
    @patch("song_shake.features.songs.routes_playlists.storage.get_all_history")
    def test_marks_active_tasks(self, mock_history, mock_jobs, mock_data_api, mock_get_yt, mock_tokens):
        """Should flag playlists with active enrichment tasks."""
        mock_get_yt.return_value = _mock_ytmusic()
        mock_tokens.return_value = {"access_token": "fake_token"}
        mock_data_api.return_value = list(SAMPLE_PLAYLISTS)
        mock_history.return_value = {}
        mock_jobs.return_value = {
            "PL_abc": {"id": "job_PL_abc_a1b2c3d4", "status": "running", "playlist_id": "PL_abc"}
        }

        response = client.get("/playlists")

        data = response.json()
        pl_abc = next(p for p in data if p["playlistId"] == "PL_abc")
        assert pl_abc["is_running"] is True
        assert pl_abc["active_task_id"] == "job_PL_abc_a1b2c3d4"

    def test_returns_401_when_not_authenticated(self):
        """Should return 401 when JWT auth fails."""
        from fastapi import HTTPException

        def _raise_401():
            raise HTTPException(status_code=401, detail="Authentication required")

        app.dependency_overrides[get_current_user] = _raise_401

        response = client.get("/playlists")

        assert response.status_code == 401

    @patch("song_shake.features.songs.routes_playlists.token_store.get_google_tokens")
    @patch("song_shake.features.songs.routes_playlists.get_authenticated_ytmusic")
    @patch("song_shake.features.songs.routes_playlists.auth.get_data_api_playlists")
    @patch("song_shake.features.songs.routes_playlists.job_storage.get_all_active_jobs")
    @patch("song_shake.features.songs.routes_playlists.storage.get_all_history")
    def test_falls_back_to_ytmusicapi(self, mock_history, mock_tasks, mock_data_api, mock_get_yt, mock_tokens):
        """Should fallback to ytmusicapi when Data API fails."""
        yt = _mock_ytmusic()
        mock_get_yt.return_value = yt
        mock_tokens.return_value = {"access_token": "fake_token"}
        mock_data_api.side_effect = Exception("Data API error")
        mock_history.return_value = {}
        mock_tasks.return_value = {}

        response = client.get("/playlists")

        assert response.status_code == 200
        yt.get_library_playlists.assert_called_once()

    @patch("song_shake.features.songs.routes_playlists.token_store.get_google_tokens")
    @patch("song_shake.features.songs.routes_playlists.get_authenticated_ytmusic")
    @patch("song_shake.features.songs.routes_playlists.auth.get_data_api_playlists")
    @patch("song_shake.features.songs.routes_playlists.job_storage.get_all_active_jobs")
    @patch("song_shake.features.songs.routes_playlists.storage.get_all_history")
    def test_handles_history_merge_error_gracefully(self, mock_history, mock_tasks, mock_data_api, mock_get_yt, mock_tokens):
        """Should return playlists even when history merge fails."""
        mock_get_yt.return_value = _mock_ytmusic()
        mock_tokens.return_value = {"access_token": "fake_token"}
        mock_data_api.return_value = list(SAMPLE_PLAYLISTS)
        mock_history.side_effect = Exception("DB error")

        response = client.get("/playlists")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2  # playlists returned despite history error
