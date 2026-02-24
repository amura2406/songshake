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
    mock.delete_tracks.return_value = 0
    mock.get_all_tracks_with_tags.return_value = (
        tracks if tracks is not None else [],
        tags if tags is not None else [],
    )
    # Strategy B: paginated + tag counts
    mock.get_paginated_tracks.return_value = (
        tracks if tracks is not None else [],
        None,  # no next cursor
    )
    raw_tag_counts = {}
    if tracks:
        raw_tag_counts["total"] = len(tracks)
        for t in tracks:
            s = t.get("status", "error")
            sk = f"status.{'Success' if s == 'success' else 'Failed'}"
            raw_tag_counts[sk] = raw_tag_counts.get(sk, 0) + 1
            for g in t.get("genres", []):
                raw_tag_counts[f"genres.{g}"] = raw_tag_counts.get(f"genres.{g}", 0) + 1
            for m in t.get("moods", []):
                raw_tag_counts[f"moods.{m}"] = raw_tag_counts.get(f"moods.{m}", 0) + 1
            for i in t.get("instruments", []):
                raw_tag_counts[f"instruments.{i}"] = raw_tag_counts.get(f"instruments.{i}", 0) + 1
    mock.get_tag_counts.return_value = raw_tag_counts
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


# --- delete_songs tests ---


class TestDeleteSongs:
    """Tests for DELETE /songs."""

    def test_deletes_songs(self):
        """Should call storage.delete_tracks with correct args."""
        mock_storage = _make_mock_storage()
        mock_storage.delete_tracks.return_value = 2
        app.dependency_overrides[get_songs_storage] = lambda: mock_storage

        response = client.request(
            "DELETE", "/api/songs", json={"video_ids": ["vid1", "vid2"]}
        )

        assert response.status_code == 200
        assert response.json() == {"deleted": 2}
        mock_storage.delete_tracks.assert_called_once_with(
            owner="test_user_123", video_ids=["vid1", "vid2"]
        )

    def test_returns_401_without_auth(self):
        """Should return 401 when no JWT is provided."""
        app.dependency_overrides.clear()
        response = client.request(
            "DELETE", "/api/songs", json={"video_ids": ["vid1"]}
        )
        assert response.status_code == 401

    def test_rejects_empty_video_ids(self):
        """Should reject request with empty video_ids list."""
        mock_storage = _make_mock_storage()
        app.dependency_overrides[get_songs_storage] = lambda: mock_storage

        response = client.request(
            "DELETE", "/api/songs", json={"video_ids": []}
        )
        assert response.status_code == 422

    def test_rejects_missing_video_ids(self):
        """Should reject request without video_ids field."""
        mock_storage = _make_mock_storage()
        app.dependency_overrides[get_songs_storage] = lambda: mock_storage

        response = client.request("DELETE", "/api/songs", json={})
        assert response.status_code == 422

    def test_returns_zero_for_nonexistent_tracks(self):
        """Should return deleted=0 when tracks don't exist."""
        mock_storage = _make_mock_storage()
        mock_storage.delete_tracks.return_value = 0
        app.dependency_overrides[get_songs_storage] = lambda: mock_storage

        response = client.request(
            "DELETE", "/api/songs", json={"video_ids": ["nonexistent"]}
        )

        assert response.status_code == 200
        assert response.json() == {"deleted": 0}


# --- get_songs_with_tags tests ---


class TestGetSongsWithTags:
    """Tests for GET /songs-with-tags."""

    def test_returns_songs_and_tags(self):
        """Should return songs from cache and tags from pre-computed counts."""
        mock_storage = _make_mock_storage(tracks=SAMPLE_TRACKS, tags=SAMPLE_TAGS)
        app.dependency_overrides[get_songs_storage] = lambda: mock_storage

        response = client.get("/api/songs-with-tags")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 3
        assert data["total"] == 3
        # Should use cached full-scan
        mock_storage.get_all_tracks.assert_called_once_with(owner="test_user_123")
        # Should use pre-computed tag counts
        mock_storage.get_tag_counts.assert_called_once_with("test_user_123")

    def test_tag_filter_uses_same_cached_path(self):
        """Should use cached full-scan even with filters active."""
        mock_storage = _make_mock_storage(tracks=SAMPLE_TRACKS, tags=SAMPLE_TAGS)
        app.dependency_overrides[get_songs_storage] = lambda: mock_storage

        response = client.get("/api/songs-with-tags?tags=Rock")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["videoId"] == "vid1"
        mock_storage.get_all_tracks.assert_called_once()

    def test_bpm_filter_works(self):
        """Should filter by BPM from cached data."""
        mock_storage = _make_mock_storage(tracks=SAMPLE_TRACKS, tags=SAMPLE_TAGS)
        app.dependency_overrides[get_songs_storage] = lambda: mock_storage

        response = client.get("/api/songs-with-tags?min_bpm=100")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["videoId"] == "vid1"

    def test_tag_counts_response_format(self):
        """Should format pre-computed tag counts correctly."""
        mock_storage = _make_mock_storage(tracks=SAMPLE_TRACKS, tags=SAMPLE_TAGS)
        app.dependency_overrides[get_songs_storage] = lambda: mock_storage

        response = client.get("/api/songs-with-tags")

        assert response.status_code == 200
        data = response.json()
        tags = data["tags"]
        assert len(tags) > 0
        for tag in tags:
            assert "name" in tag
            assert "type" in tag
            assert "count" in tag
            assert tag["type"] in ("genre", "mood", "instrument", "status")

    def test_pagination_offset(self):
        """Should paginate from cached data using skip/limit."""
        mock_storage = _make_mock_storage(tracks=SAMPLE_TRACKS, tags=SAMPLE_TAGS)
        app.dependency_overrides[get_songs_storage] = lambda: mock_storage

        response = client.get("/api/songs-with-tags?skip=1&limit=1")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["total"] == 3

    def test_falls_back_when_tag_counts_empty(self):
        """Should fall back to get_all_tracks_with_tags when tag_counts is empty."""
        mock_storage = _make_mock_storage(tracks=SAMPLE_TRACKS, tags=SAMPLE_TAGS)
        mock_storage.get_tag_counts.return_value = {}  # empty = never built
        app.dependency_overrides[get_songs_storage] = lambda: mock_storage

        response = client.get("/api/songs-with-tags")

        assert response.status_code == 200
        data = response.json()
        assert len(data["tags"]) == 6  # falls back to computed tags


class TestFormatTagCounts:
    """Tests for _format_tag_counts pure function."""

    def test_converts_flat_dict_to_sorted_list(self):
        """Should convert flat tag_counts dict to sorted TagResponse list."""
        from song_shake.features.songs.routes import _format_tag_counts

        raw = {
            "genres.Rock": 45,
            "genres.Pop": 32,
            "moods.Energetic": 28,
            "status.Success": 950,
            "total": 962,
        }
        result = _format_tag_counts(raw)

        assert len(result) == 4  # total excluded
        # Sorted by count descending
        assert result[0] == {"name": "Success", "type": "status", "count": 950}
        assert result[1] == {"name": "Rock", "type": "genre", "count": 45}
        assert result[2] == {"name": "Pop", "type": "genre", "count": 32}
        assert result[3] == {"name": "Energetic", "type": "mood", "count": 28}

    def test_skips_zero_counts(self):
        """Should exclude tags with zero or negative counts."""
        from song_shake.features.songs.routes import _format_tag_counts

        raw = {"genres.Rock": 0, "genres.Pop": -1, "moods.Chill": 5, "total": 5}
        result = _format_tag_counts(raw)

        assert len(result) == 1
        assert result[0]["name"] == "Chill"

    def test_handles_empty_dict(self):
        """Should return empty list for empty dict."""
        from song_shake.features.songs.routes import _format_tag_counts

        assert _format_tag_counts({}) == []

    def test_singularizes_type_names(self):
        """Should convert 'genres' -> 'genre', 'moods' -> 'mood', etc."""
        from song_shake.features.songs.routes import _format_tag_counts

        raw = {
            "genres.Rock": 1,
            "moods.Happy": 1,
            "instruments.Guitar": 1,
            "status.Success": 1,
        }
        result = _format_tag_counts(raw)
        types = {r["type"] for r in result}
        assert types == {"genre", "mood", "instrument", "status"}
