"""Unit tests for songs route handlers."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from song_shake.api import app
from song_shake.features.auth.dependencies import get_current_user
from song_shake.platform.storage_factory import get_songs_storage

client = TestClient(app)

FAKE_USER = {"sub": "test_user_123", "name": "Test User", "thumb": None}


def _make_mock_storage(tracks=None, tags=None):
    """Create a mock StoragePort."""
    mock = MagicMock()
    mock.get_all_tracks.return_value = tracks if tracks is not None else []
    mock.get_tags.return_value = tags if tags is not None else []
    return mock


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

    def test_returns_all_tracks(self):
        """Should return all tracks for the authenticated user."""
        mock_storage = _make_mock_storage(tracks=SAMPLE_TRACKS)
        app.dependency_overrides[get_songs_storage] = lambda: mock_storage

        response = client.get("/api/songs")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 3
        assert data["total"] == 3
        assert data["page"] == 0
        assert data["pages"] == 1
        mock_storage.get_all_tracks.assert_called_once_with(owner="test_user_123")

    def test_returns_empty_list_when_no_tracks(self):
        """Should return empty list when owner has no tracks."""
        mock_storage = _make_mock_storage(tracks=[])
        app.dependency_overrides[get_songs_storage] = lambda: mock_storage

        response = client.get("/api/songs")

        assert response.status_code == 200
        assert response.json()["items"] == []
        assert response.json()["total"] == 0

    def test_uses_jwt_user_id_as_owner(self):
        """Should use the JWT sub claim as the owner (ignoring any query param)."""
        mock_storage = _make_mock_storage(tracks=[])
        app.dependency_overrides[get_songs_storage] = lambda: mock_storage

        response = client.get("/api/songs")

        mock_storage.get_all_tracks.assert_called_once_with(owner="test_user_123")

    def test_pagination_skip_and_limit(self):
        """Should apply skip and limit for pagination."""
        mock_storage = _make_mock_storage(tracks=SAMPLE_TRACKS)
        app.dependency_overrides[get_songs_storage] = lambda: mock_storage

        response = client.get("/api/songs?skip=1&limit=1")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["videoId"] == "vid2"
        assert data["total"] == 3

    def test_filters_by_min_bpm(self):
        """Should exclude tracks with BPM below min_bpm."""
        mock_storage = _make_mock_storage(tracks=SAMPLE_TRACKS)
        app.dependency_overrides[get_songs_storage] = lambda: mock_storage

        response = client.get("/api/songs?min_bpm=100")

        assert response.status_code == 200
        data = response.json()
        # Only vid1 (bpm=120) passes; vid2 (90) excluded, vid3 (None) excluded
        assert len(data["items"]) == 1
        assert data["items"][0]["videoId"] == "vid1"

    def test_filters_by_max_bpm(self):
        """Should exclude tracks with BPM above max_bpm."""
        mock_storage = _make_mock_storage(tracks=SAMPLE_TRACKS)
        app.dependency_overrides[get_songs_storage] = lambda: mock_storage

        response = client.get("/api/songs?max_bpm=100")

        assert response.status_code == 200
        data = response.json()
        # Only vid2 (bpm=90) passes
        assert len(data["items"]) == 1
        assert data["items"][0]["videoId"] == "vid2"

    def test_filters_by_bpm_range(self):
        """Should filter tracks within BPM range."""
        mock_storage = _make_mock_storage(tracks=SAMPLE_TRACKS)
        app.dependency_overrides[get_songs_storage] = lambda: mock_storage

        response = client.get("/api/songs?min_bpm=80&max_bpm=100")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["videoId"] == "vid2"

    def test_filters_by_tag(self):
        """Should filter tracks that have all specified tags."""
        mock_storage = _make_mock_storage(tracks=SAMPLE_TRACKS)
        app.dependency_overrides[get_songs_storage] = lambda: mock_storage

        response = client.get("/api/songs?tags=Rock")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["videoId"] == "vid1"

    def test_filters_by_multiple_tags(self):
        """Should require ALL tags to be present (intersection)."""
        mock_storage = _make_mock_storage(tracks=SAMPLE_TRACKS)
        app.dependency_overrides[get_songs_storage] = lambda: mock_storage

        response = client.get("/api/songs?tags=Rock,Energetic")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["videoId"] == "vid1"

    def test_filters_by_status_tag(self):
        """Should support Success/Failed as virtual status tags."""
        mock_storage = _make_mock_storage(tracks=SAMPLE_TRACKS)
        app.dependency_overrides[get_songs_storage] = lambda: mock_storage

        response = client.get("/api/songs?tags=Success")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2  # vid1 and vid2

    def test_rejects_invalid_skip(self):
        """Should reject negative skip values."""
        response = client.get("/api/songs?skip=-1")
        assert response.status_code == 422

    def test_rejects_invalid_limit(self):
        """Should reject limit values outside allowed range."""
        response = client.get("/api/songs?limit=0")
        assert response.status_code == 422

        response = client.get("/api/songs?limit=201")
        assert response.status_code == 422

    def test_rejects_invalid_bpm(self):
        """Should reject BPM values outside allowed range."""
        response = client.get("/api/songs?min_bpm=0")
        assert response.status_code == 422

        response = client.get("/api/songs?max_bpm=301")
        assert response.status_code == 422

    def test_returns_401_without_auth(self):
        """Should return 401 when no JWT is provided."""
        app.dependency_overrides.clear()
        response = client.get("/api/songs")
        assert response.status_code == 401


# --- get_tags tests ---


class TestGetTags:
    """Tests for GET /tags."""

    def test_returns_tags(self):
        """Should return tags from storage."""
        mock_storage = _make_mock_storage(tags=SAMPLE_TAGS)
        app.dependency_overrides[get_songs_storage] = lambda: mock_storage

        response = client.get("/api/tags")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 6
        mock_storage.get_tags.assert_called_once_with(owner="test_user_123")

    def test_uses_jwt_user_as_owner(self):
        """Should use JWT sub as owner, not query params."""
        mock_storage = _make_mock_storage(tags=[])
        app.dependency_overrides[get_songs_storage] = lambda: mock_storage

        response = client.get("/api/tags")

        mock_storage.get_tags.assert_called_once_with(owner="test_user_123")

    def test_returns_empty_list(self):
        """Should return empty list when no tags exist."""
        mock_storage = _make_mock_storage(tags=[])
        app.dependency_overrides[get_songs_storage] = lambda: mock_storage

        response = client.get("/api/tags")

        assert response.status_code == 200
        assert response.json() == []
