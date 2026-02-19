"""Unit tests for songs route handlers."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from song_shake.api import app
from song_shake.features.auth.dependencies import get_current_user

client = TestClient(app)

FAKE_USER = {"sub": "test_user_123", "name": "Test User", "thumb": None}


@pytest.fixture(autouse=True)
def _override_auth():
    """Override auth dependency for all tests."""
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    yield
    app.dependency_overrides.clear()


# --- Fixtures ---


SAMPLE_TRACKS = [
    {
        "videoId": "vid1",
        "title": "Rock Anthem",
        "artists": "Band A",
        "genres": ["Rock"],
        "moods": ["Energetic"],
        "instruments": ["Guitar"],
        "bpm": 120,
        "status": "success",
    },
    {
        "videoId": "vid2",
        "title": "Chill Vibes",
        "artists": "Artist B",
        "genres": ["Electronic"],
        "moods": ["Chill"],
        "instruments": ["Synth"],
        "bpm": 90,
        "status": "success",
    },
    {
        "videoId": "vid3",
        "title": "Failed Track",
        "artists": "Artist C",
        "genres": [],
        "moods": [],
        "instruments": [],
        "bpm": None,
        "status": "error",
        "error_message": "Download failed",
    },
]

SAMPLE_TAGS = [
    {"name": "Success", "type": "status", "count": 2},
    {"name": "Failed", "type": "status", "count": 1},
    {"name": "Rock", "type": "genre", "count": 1},
    {"name": "Electronic", "type": "genre", "count": 1},
    {"name": "Energetic", "type": "mood", "count": 1},
    {"name": "Chill", "type": "mood", "count": 1},
]


# --- get_songs tests ---


class TestGetSongs:
    """Tests for GET /songs."""

    @patch("song_shake.features.songs.routes.storage.get_all_tracks")
    def test_returns_all_tracks(self, mock_get_tracks):
        """Should return all tracks for the authenticated user."""
        mock_get_tracks.return_value = SAMPLE_TRACKS

        response = client.get("/songs")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        mock_get_tracks.assert_called_once_with(owner="test_user_123")

    @patch("song_shake.features.songs.routes.storage.get_all_tracks")
    def test_returns_empty_list_when_no_tracks(self, mock_get_tracks):
        """Should return empty list when owner has no tracks."""
        mock_get_tracks.return_value = []

        response = client.get("/songs")

        assert response.status_code == 200
        assert response.json() == []

    @patch("song_shake.features.songs.routes.storage.get_all_tracks")
    def test_uses_jwt_user_id_as_owner(self, mock_get_tracks):
        """Should use the JWT sub claim as the owner (ignoring any query param)."""
        mock_get_tracks.return_value = []

        response = client.get("/songs")

        mock_get_tracks.assert_called_once_with(owner="test_user_123")

    @patch("song_shake.features.songs.routes.storage.get_all_tracks")
    def test_pagination_skip_and_limit(self, mock_get_tracks):
        """Should apply skip and limit for pagination."""
        mock_get_tracks.return_value = SAMPLE_TRACKS

        response = client.get("/songs?skip=1&limit=1")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["videoId"] == "vid2"

    @patch("song_shake.features.songs.routes.storage.get_all_tracks")
    def test_filters_by_min_bpm(self, mock_get_tracks):
        """Should exclude tracks with BPM below min_bpm."""
        mock_get_tracks.return_value = SAMPLE_TRACKS

        response = client.get("/songs?min_bpm=100")

        assert response.status_code == 200
        data = response.json()
        # Only vid1 (bpm=120) passes; vid2 (90) excluded, vid3 (None) excluded
        assert len(data) == 1
        assert data[0]["videoId"] == "vid1"

    @patch("song_shake.features.songs.routes.storage.get_all_tracks")
    def test_filters_by_max_bpm(self, mock_get_tracks):
        """Should exclude tracks with BPM above max_bpm."""
        mock_get_tracks.return_value = SAMPLE_TRACKS

        response = client.get("/songs?max_bpm=100")

        assert response.status_code == 200
        data = response.json()
        # Only vid2 (bpm=90) passes
        assert len(data) == 1
        assert data[0]["videoId"] == "vid2"

    @patch("song_shake.features.songs.routes.storage.get_all_tracks")
    def test_filters_by_bpm_range(self, mock_get_tracks):
        """Should filter tracks within BPM range."""
        mock_get_tracks.return_value = SAMPLE_TRACKS

        response = client.get("/songs?min_bpm=80&max_bpm=100")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["videoId"] == "vid2"

    @patch("song_shake.features.songs.routes.storage.get_all_tracks")
    def test_filters_by_tag(self, mock_get_tracks):
        """Should filter tracks that have all specified tags."""
        mock_get_tracks.return_value = SAMPLE_TRACKS

        response = client.get("/songs?tags=Rock")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["videoId"] == "vid1"

    @patch("song_shake.features.songs.routes.storage.get_all_tracks")
    def test_filters_by_multiple_tags(self, mock_get_tracks):
        """Should require ALL tags to be present (intersection)."""
        mock_get_tracks.return_value = SAMPLE_TRACKS

        response = client.get("/songs?tags=Rock,Energetic")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["videoId"] == "vid1"

    @patch("song_shake.features.songs.routes.storage.get_all_tracks")
    def test_filters_by_status_tag(self, mock_get_tracks):
        """Should support Success/Failed as virtual status tags."""
        mock_get_tracks.return_value = SAMPLE_TRACKS

        response = client.get("/songs?tags=Success")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2  # vid1 and vid2

    def test_rejects_invalid_skip(self):
        """Should reject negative skip values."""
        response = client.get("/songs?skip=-1")
        assert response.status_code == 422

    def test_rejects_invalid_limit(self):
        """Should reject limit values outside allowed range."""
        response = client.get("/songs?limit=0")
        assert response.status_code == 422

        response = client.get("/songs?limit=201")
        assert response.status_code == 422

    def test_rejects_invalid_bpm(self):
        """Should reject BPM values outside allowed range."""
        response = client.get("/songs?min_bpm=0")
        assert response.status_code == 422

        response = client.get("/songs?max_bpm=301")
        assert response.status_code == 422

    def test_returns_401_without_auth(self):
        """Should return 401 when no JWT is provided."""
        app.dependency_overrides.clear()
        response = client.get("/songs")
        assert response.status_code == 401


# --- get_tags tests ---


class TestGetTags:
    """Tests for GET /tags."""

    @patch("song_shake.features.songs.routes.storage.get_tags")
    def test_returns_tags(self, mock_get_tags):
        """Should return tags from storage."""
        mock_get_tags.return_value = SAMPLE_TAGS

        response = client.get("/tags")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 6
        mock_get_tags.assert_called_once_with(owner="test_user_123")

    @patch("song_shake.features.songs.routes.storage.get_tags")
    def test_uses_jwt_user_as_owner(self, mock_get_tags):
        """Should use JWT sub as owner, not query params."""
        mock_get_tags.return_value = []

        response = client.get("/tags")

        mock_get_tags.assert_called_once_with(owner="test_user_123")

    @patch("song_shake.features.songs.routes.storage.get_tags")
    def test_returns_empty_list(self, mock_get_tags):
        """Should return empty list when no tags exist."""
        mock_get_tags.return_value = []

        response = client.get("/tags")

        assert response.status_code == 200
        assert response.json() == []
