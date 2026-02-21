"""Unit tests for vibing business logic (pure functions)."""

from datetime import datetime, timezone

from song_shake.features.vibing.logic import (
    build_final_playlist,
    extract_artist_string,
    minify_catalog,
    pre_sort_by_bpm,
    select_seed_track,
    validate_no_cross_playlist_duplicates,
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
            "instruments": ["Guitar", "Piano"],
            "vocalType": "Vocals",
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
    assert item["instruments"] == ["Guitar", "Piano"]
    assert item["vocalType"] == "Vocals"
    assert "thumbnails" not in item
    assert "album" not in item
    assert "year" not in item
    assert "status" not in item


def test_minify_catalog_string_artists():
    """Handles legacy string artist format."""
    tracks = [{"videoId": "x", "title": "T", "artists": "Legacy Artist"}]
    result = minify_catalog(tracks)
    assert result[0]["artist_names"] == ["Legacy Artist"]


def test_minify_catalog_includes_instruments_and_vocal_type():
    """New fields instruments and vocalType are included."""
    tracks = [
        {"videoId": "a", "title": "A", "instruments": ["Synth"], "vocalType": "Instrumental"},
        {"videoId": "b", "title": "B"},  # no instruments/vocalType
    ]
    result = minify_catalog(tracks)
    assert result[0]["instruments"] == ["Synth"]
    assert result[0]["vocalType"] == "Instrumental"
    assert result[1]["instruments"] == []
    assert result[1]["vocalType"] is None


# ---------------------------------------------------------------------------
# pre_sort_by_bpm
# ---------------------------------------------------------------------------


def test_pre_sort_by_bpm_ascending():
    """Tracks are sorted by BPM ascending."""
    tracks = [
        {"videoId": "a", "bpm": 140},
        {"videoId": "b", "bpm": 90},
        {"videoId": "c", "bpm": 120},
    ]
    result = pre_sort_by_bpm(tracks)
    assert [t["videoId"] for t in result] == ["b", "c", "a"]


def test_pre_sort_by_bpm_none_last():
    """Tracks without BPM are placed at the end."""
    tracks = [
        {"videoId": "a", "bpm": None},
        {"videoId": "b", "bpm": 100},
        {"videoId": "c"},  # missing bpm key
        {"videoId": "d", "bpm": 80},
    ]
    result = pre_sort_by_bpm(tracks)
    assert result[0]["videoId"] == "d"
    assert result[1]["videoId"] == "b"
    # None/missing at the end
    assert {t["videoId"] for t in result[2:]} == {"a", "c"}


def test_pre_sort_by_bpm_all_none():
    """All None BPMs preserves original order (stable sort)."""
    tracks = [
        {"videoId": "a"},
        {"videoId": "b"},
    ]
    result = pre_sort_by_bpm(tracks)
    assert [t["videoId"] for t in result] == ["a", "b"]


# ---------------------------------------------------------------------------
# validate_no_cross_playlist_duplicates
# ---------------------------------------------------------------------------


def test_validate_no_duplicates_clean():
    """No duplicates across playlists — returns unchanged."""
    playlists = [
        {"curated_video_ids": ["a", "b", "c"]},
        {"curated_video_ids": ["d", "e", "f"]},
    ]
    result = validate_no_cross_playlist_duplicates(playlists, track_limit=0)
    assert result[0]["curated_video_ids"] == ["a", "b", "c"]
    assert result[1]["curated_video_ids"] == ["d", "e", "f"]


def test_validate_removes_cross_duplicates():
    """Duplicates in later playlists are silently removed."""
    playlists = [
        {"curated_video_ids": ["a", "b"]},
        {"curated_video_ids": ["b", "c", "a", "d"]},  # b and a are dupes
    ]
    result = validate_no_cross_playlist_duplicates(playlists, track_limit=0)
    assert result[0]["curated_video_ids"] == ["a", "b"]
    assert result[1]["curated_video_ids"] == ["c", "d"]


def test_validate_enforces_track_limit():
    """Each playlist is capped at track_limit."""
    playlists = [
        {"curated_video_ids": ["a", "b", "c", "d", "e"]},
    ]
    result = validate_no_cross_playlist_duplicates(playlists, track_limit=3)
    assert len(result[0]["curated_video_ids"]) == 3
    assert result[0]["curated_video_ids"] == ["a", "b", "c"]


def test_validate_dedup_within_single_playlist():
    """Duplicate IDs within the same playlist are removed."""
    playlists = [
        {"curated_video_ids": ["a", "b", "a", "c"]},
    ]
    result = validate_no_cross_playlist_duplicates(playlists, track_limit=0)
    assert result[0]["curated_video_ids"] == ["a", "b", "c"]


def test_validate_limit_zero_means_no_limit():
    """track_limit=0 means no limit."""
    playlists = [
        {"curated_video_ids": ["a", "b", "c", "d", "e", "f"]},
    ]
    result = validate_no_cross_playlist_duplicates(playlists, track_limit=0)
    assert len(result[0]["curated_video_ids"]) == 6


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
