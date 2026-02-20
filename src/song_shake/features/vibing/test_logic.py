"""Unit tests for vibing business logic (pure functions)."""

from datetime import datetime, timezone

from song_shake.features.vibing.logic import (
    build_final_playlist,
    extract_artist_string,
    minify_catalog,
    select_seed_track,
)


# ---------------------------------------------------------------------------
# select_seed_track
# ---------------------------------------------------------------------------


def test_select_seed_no_playlisted_at():
    """Tracks without last_playlisted_at are treated as oldest."""
    tracks = [
        {"videoId": "a", "title": "A", "last_playlisted_at": datetime(2024, 1, 1, tzinfo=timezone.utc)},
        {"videoId": "b", "title": "B"},  # None → oldest
        {"videoId": "c", "title": "C", "last_playlisted_at": datetime(2023, 6, 1, tzinfo=timezone.utc)},
    ]
    seed, remaining = select_seed_track(tracks)
    assert seed["videoId"] == "b"
    assert len(remaining) == 2


def test_select_seed_oldest_wins():
    """Track with the oldest timestamp is selected."""
    tracks = [
        {"videoId": "a", "last_playlisted_at": datetime(2024, 3, 1, tzinfo=timezone.utc)},
        {"videoId": "b", "last_playlisted_at": datetime(2024, 1, 1, tzinfo=timezone.utc)},
        {"videoId": "c", "last_playlisted_at": datetime(2024, 2, 1, tzinfo=timezone.utc)},
    ]
    seed, remaining = select_seed_track(tracks)
    assert seed["videoId"] == "b"


def test_select_seed_all_none():
    """When all are None the first (by stable sort) is picked."""
    tracks = [
        {"videoId": "x", "title": "X"},
        {"videoId": "y", "title": "Y"},
    ]
    seed, remaining = select_seed_track(tracks)
    assert seed["videoId"] == "x"
    assert len(remaining) == 1


def test_select_seed_single_track():
    """A single track returns it as seed with empty remaining."""
    tracks = [{"videoId": "only", "title": "Only One"}]
    seed, remaining = select_seed_track(tracks)
    assert seed["videoId"] == "only"
    assert remaining == []


def test_select_seed_empty_raises():
    """Empty track list raises ValueError."""
    try:
        select_seed_track([])
        assert False, "Should have raised"
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# minify_catalog
# ---------------------------------------------------------------------------


def test_minify_catalog_drops_heavy_fields():
    """Thumbnails, album, year, etc. are stripped."""
    tracks = [
        {
            "videoId": "abc",
            "title": "Song A",
            "artists": [{"name": "Artist1", "id": "ch1"}],
            "genres": ["Pop"],
            "moods": ["Happy"],
            "bpm": 120,
            "thumbnails": [{"url": "http://...", "width": 120}],
            "album": {"name": "Album1"},
            "year": "2024",
            "status": "success",
        }
    ]
    result = minify_catalog(tracks)
    assert len(result) == 1
    item = result[0]
    assert item["videoId"] == "abc"
    assert item["artist_names"] == ["Artist1"]
    assert "thumbnails" not in item
    assert "album" not in item
    assert "year" not in item
    assert "status" not in item


def test_minify_catalog_string_artists():
    """Handles legacy string artist format."""
    tracks = [{"videoId": "x", "title": "T", "artists": "Legacy Artist"}]
    result = minify_catalog(tracks)
    assert result[0]["artist_names"] == ["Legacy Artist"]


# ---------------------------------------------------------------------------
# build_final_playlist
# ---------------------------------------------------------------------------


def test_build_final_playlist_basic():
    """Seed + curated IDs combined correctly."""
    result = build_final_playlist("seed1", ["a", "b", "c"])
    assert result == ["seed1", "a", "b", "c"]


def test_build_final_playlist_deduplicates():
    """Seed is not duplicated if it appears in curated list."""
    result = build_final_playlist("seed1", ["seed1", "a", "b"])
    assert result == ["seed1", "a", "b"]


def test_build_final_playlist_removes_dupes_in_curated():
    """Duplicate curated IDs are removed."""
    result = build_final_playlist("seed1", ["a", "b", "a", "c"])
    assert result == ["seed1", "a", "b", "c"]


# ---------------------------------------------------------------------------
# extract_artist_string
# ---------------------------------------------------------------------------


def test_extract_artist_string_list_of_dicts():
    track = {"artists": [{"name": "A"}, {"name": "B"}]}
    assert extract_artist_string(track) == "A, B"


def test_extract_artist_string_legacy():
    track = {"artists": "Solo Artist"}
    assert extract_artist_string(track) == "Solo Artist"


def test_extract_artist_string_empty():
    assert extract_artist_string({}) == "Unknown"
