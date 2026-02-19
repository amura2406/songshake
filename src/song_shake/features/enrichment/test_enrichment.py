"""Unit tests for enrichment module — TokenTracker + process_playlist with mock adapters."""

import pytest

from song_shake.features.enrichment.enrichment import (
    TokenTracker,
    _build_track_data,
    process_playlist,
)


# ---------------------------------------------------------------------------
# Test helpers — lightweight mock adapters implementing the Protocols
# ---------------------------------------------------------------------------

class FakeStorage:
    """In-memory StoragePort for testing."""

    def __init__(self, existing_tracks: dict | None = None):
        # existing_tracks: dict keyed by videoId
        self._tracks: dict[str, dict] = dict(existing_tracks) if existing_tracks else {}
        self._history: list[dict] = []
        self.wipe_called = False

    def wipe_db(self) -> None:
        self._tracks.clear()
        self._history.clear()
        self.wipe_called = True

    def save_track(self, track_data: dict) -> None:
        vid = track_data.get("videoId")
        if vid:
            self._tracks[vid] = track_data

    def get_all_tracks(self, owner: str) -> list[dict]:
        return [t for t in self._tracks.values() if t.get("owner") == owner]

    def get_track_by_id(self, video_id: str) -> dict | None:
        return self._tracks.get(video_id)

    def get_tags(self, owner: str) -> list[dict]:
        return []

    def save_enrichment_history(
        self, playlist_id: str, owner: str, metadata: dict
    ) -> None:
        self._history.append(
            {"playlist_id": playlist_id, "owner": owner, **metadata}
        )

    def get_enrichment_history(self, owner: str) -> dict:
        return {}


class FakePlaylistFetcher:
    """Returns pre-configured tracks list."""

    def __init__(self, tracks: list[dict]):
        self._tracks = tracks

    def get_tracks(self, playlist_id: str) -> list[dict]:
        return self._tracks

    def get_title(self, playlist_id: str) -> str:
        return "Test Playlist"


class FakeDownloader:
    """Returns a fake filepath. Records calls."""

    def __init__(self):
        self.calls: list[str] = []

    def download(self, video_id: str, output_dir: str) -> str:
        self.calls.append(video_id)
        return f"{output_dir}/{video_id}.mp3"


class FakeDownloaderRaises:
    """Simulates a download failure."""

    def __init__(self, error_msg: str = "Download failed"):
        self.error_msg = error_msg

    def download(self, video_id: str, output_dir: str) -> str:
        raise RuntimeError(self.error_msg)


class FakeEnricher:
    """Returns pre-configured enrichment result. Records calls."""

    def __init__(self, result: dict | None = None):
        self._result = result or {
            "genres": ["Pop"],
            "moods": ["Happy"],
            "instruments": ["Guitar"],
            "bpm": 120,
            "usage_metadata": {"prompt_tokens": 100, "candidates_tokens": 50},
        }
        self.calls: list[tuple[str, str, str]] = []

    def enrich(self, file_path: str, title: str, artist: str) -> dict:
        self.calls.append((file_path, title, artist))
        # Return a copy so each call gets its own dict
        return dict(self._result)


class FakeEnricherError:
    """Returns enrichment result with an error."""

    def enrich(self, file_path: str, title: str, artist: str) -> dict:
        return {
            "genres": ["Error"],
            "moods": ["Error"],
            "instruments": [],
            "bpm": None,
            "error": "AI model failed",
            "usage_metadata": {"prompt_tokens": 10, "candidates_tokens": 0},
        }


class FakeSongFetcher:
    """Returns pre-configured song metadata."""

    def __init__(self, is_music: bool = True):
        self._is_music = is_music

    def get_song(self, video_id: str) -> dict:
        return {
            "isMusic": self._is_music,
            "artists": [{"name": "Test Artist", "id": "UC_test"}],
            "album": {"name": "Test Album", "id": "MPRE_test"},
            "year": "2024",
            "playCount": "3.5M",
            "channelId": "UC_test",
        }


class FakeAlbumFetcher:
    """Returns pre-configured album metadata."""

    def __init__(self, year: str | None = "2024"):
        self._year = year

    def get_album(self, browse_id: str) -> dict:
        return {"year": self._year}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_track(video_id: str, title: str = "Song", artist: str = "Artist") -> dict:
    """Create a minimal playlist track dict matching YouTube Music format."""
    return {
        "videoId": video_id,
        "title": title,
        "artists": [{"name": artist}],
        "album": {"name": "Album"},
        "thumbnails": [],
    }


# ===========================================================================
# TokenTracker tests
# ===========================================================================


class TestTokenTracker:
    """Tests for TokenTracker cost calculation logic."""

    def test_initial_state(self):
        """Should start with zero counters."""
        tracker = TokenTracker()
        assert tracker.input_tokens == 0
        assert tracker.output_tokens == 0
        assert tracker.successful == 0
        assert tracker.failed == 0
        assert tracker.errors == []

    def test_get_cost_zero_tokens(self):
        """Should return 0 cost with no tokens."""
        tracker = TokenTracker()
        assert tracker.get_cost() == 0.0

    def test_get_cost_calculation(self):
        """Should calculate cost based on Gemini pricing."""
        tracker = TokenTracker()
        tracker.input_tokens = 1_000_000  # 1M input tokens
        tracker.output_tokens = 1_000_000  # 1M output tokens

        cost = tracker.get_cost()
        # Cost depends on the per-token rates in the implementation
        assert cost > 0
        assert isinstance(cost, float)

    def test_successful_and_failed_counts(self):
        """Should track successful and failed operations independently."""
        tracker = TokenTracker()
        tracker.successful = 5
        tracker.failed = 2
        tracker.errors = ["Error 1", "Error 2"]

        assert tracker.successful == 5
        assert tracker.failed == 2
        assert len(tracker.errors) == 2

    def test_add_usage_from_dict(self):
        """Should update token counts from a plain dict."""
        tracker = TokenTracker()
        tracker.add_usage_from_dict({"prompt_tokens": 200, "candidates_tokens": 100})
        assert tracker.input_tokens == 200
        assert tracker.output_tokens == 100

    def test_add_usage_from_dict_none(self):
        """Should be a no-op when passed None."""
        tracker = TokenTracker()
        tracker.add_usage_from_dict(None)
        assert tracker.input_tokens == 0

    def test_add_usage_from_dict_empty(self):
        """Should be a no-op when passed empty dict."""
        tracker = TokenTracker()
        tracker.add_usage_from_dict({})
        assert tracker.input_tokens == 0


# ===========================================================================
# _build_track_data tests (pure function)
# ===========================================================================


class TestBuildTrackData:
    """Tests for the _build_track_data pure function."""

    def test_success_track(self):
        """Should build a success track_data dict with structured artists."""
        track = _make_track("abc123", "My Song", "Dua Lipa")
        metadata = {
            "genres": ["Pop"],
            "moods": ["Happy"],
            "instruments": ["Synth"],
            "bpm": 128,
        }
        result = _build_track_data("abc123", "My Song", track, "user1", metadata)

        assert result["videoId"] == "abc123"
        assert result["title"] == "My Song"
        # artists is now a structured list
        assert isinstance(result["artists"], list)
        assert result["artists"][0]["name"] == "Dua Lipa"
        assert result["genres"] == ["Pop"]
        assert result["bpm"] == 128
        assert result["status"] == "success"
        assert result["success"] is True
        assert result["isMusic"] is True
        assert result["error_message"] is None
        assert result["owner"] == "user1"
        assert "music.youtube.com" in result["url"]

    def test_error_track(self):
        """Should build an error track_data dict when metadata has error."""
        track = _make_track("xyz789")
        metadata = {"genres": [], "moods": [], "instruments": [], "bpm": None, "error": "boom"}
        result = _build_track_data("xyz789", "Bad", track, "u", metadata)

        assert result["status"] == "error"
        assert result["success"] is False
        assert result["error_message"] == "boom"

    def test_missing_album(self):
        """Should handle track with no album gracefully."""
        track = {"videoId": "v1", "title": "T", "artists": [], "thumbnails": []}
        metadata = {"genres": [], "moods": [], "instruments": [], "bpm": None}
        result = _build_track_data("v1", "T", track, "o", metadata)
        assert result["album"] is None

    def test_non_music_track(self):
        """Should mark track as non-music when is_music=False."""
        track = _make_track("nm1", "Tutorial Video")
        metadata = {"genres": [], "moods": [], "instruments": [], "bpm": None}
        result = _build_track_data("nm1", "Tutorial Video", track, "o", metadata, is_music=False)

        assert result["isMusic"] is False
        assert result["status"] == "non-music"
        assert result["success"] is False


# ===========================================================================
# process_playlist tests (with mock adapters)
# ===========================================================================


class TestProcessPlaylist:
    """Integration-style unit tests for process_playlist using fake adapters."""

    def test_happy_path_two_new_tracks(self):
        """Should download, enrich, and save two new tracks."""
        tracks = [_make_track("v1", "Song A", "Art A"), _make_track("v2", "Song B", "Art B")]
        storage = FakeStorage()
        fetcher = FakePlaylistFetcher(tracks)
        downloader = FakeDownloader()
        enricher = FakeEnricher()

        results = process_playlist(
            "PL_TEST",
            owner="tester",
            storage_port=storage,
            playlist_fetcher=fetcher,
            audio_downloader=downloader,
            audio_enricher=enricher,
            song_fetcher=FakeSongFetcher(),
            album_fetcher=FakeAlbumFetcher(),
        )

        assert len(results) == 2
        assert all(r["status"] == "success" for r in results)
        assert len(downloader.calls) == 2
        assert len(enricher.calls) == 2
        # Both tracks saved in storage
        assert storage.get_track_by_id("v1") is not None
        assert storage.get_track_by_id("v2") is not None

    def test_deduplication_skips_cached_tracks(self):
        """Should skip download/enrich for tracks already in storage."""
        tracks = [_make_track("cached1", "Old Song")]
        existing = {"cached1": {"videoId": "cached1", "title": "Old Song", "genres": ["Rock"]}}
        storage = FakeStorage(existing_tracks=existing)
        downloader = FakeDownloader()
        enricher = FakeEnricher()

        results = process_playlist(
            "PL_DEDUP",
            owner="user",
            storage_port=storage,
            playlist_fetcher=FakePlaylistFetcher(tracks),
            audio_downloader=downloader,
            audio_enricher=enricher,
            song_fetcher=FakeSongFetcher(),
            album_fetcher=FakeAlbumFetcher(),
        )

        # Cached track is re-saved (owner link) but not downloaded or enriched
        assert len(results) == 0  # cached tracks aren't appended to results
        assert len(downloader.calls) == 0
        assert len(enricher.calls) == 0

    def test_mixed_cached_and_new(self):
        """Should process only new tracks and skip cached ones."""
        tracks = [_make_track("cached", "Old"), _make_track("new1", "New")]
        existing = {"cached": {"videoId": "cached", "title": "Old"}}
        storage = FakeStorage(existing_tracks=existing)
        downloader = FakeDownloader()
        enricher = FakeEnricher()

        results = process_playlist(
            "PL_MIX",
            owner="user",
            storage_port=storage,
            playlist_fetcher=FakePlaylistFetcher(tracks),
            audio_downloader=downloader,
            audio_enricher=enricher,
            song_fetcher=FakeSongFetcher(),
            album_fetcher=FakeAlbumFetcher(),
        )

        assert len(results) == 1
        assert results[0]["videoId"] == "new1"
        assert len(downloader.calls) == 1
        assert downloader.calls[0] == "new1"

    def test_empty_playlist(self):
        """Should return empty list when playlist has no tracks."""
        storage = FakeStorage()
        results = process_playlist(
            "PL_EMPTY",
            storage_port=storage,
            playlist_fetcher=FakePlaylistFetcher([]),
            audio_downloader=FakeDownloader(),
            audio_enricher=FakeEnricher(),
            song_fetcher=FakeSongFetcher(),
            album_fetcher=FakeAlbumFetcher(),
        )
        assert results == []

    def test_enricher_returns_error(self):
        """Should save track with error status when enricher returns error."""
        tracks = [_make_track("err1", "Bad Song")]
        storage = FakeStorage()
        downloader = FakeDownloader()
        enricher = FakeEnricherError()

        results = process_playlist(
            "PL_ERR",
            owner="user",
            storage_port=storage,
            playlist_fetcher=FakePlaylistFetcher(tracks),
            audio_downloader=downloader,
            audio_enricher=enricher,
            song_fetcher=FakeSongFetcher(),
            album_fetcher=FakeAlbumFetcher(),
        )

        assert len(results) == 1
        assert results[0]["status"] == "error"
        assert results[0]["error_message"] == "AI model failed"
        # Track still saved to storage
        assert storage.get_track_by_id("err1") is not None

    def test_download_failure(self):
        """Should catch download exception and save error track."""
        tracks = [_make_track("dl_fail", "Crash Song")]
        storage = FakeStorage()

        results = process_playlist(
            "PL_DL_FAIL",
            owner="user",
            storage_port=storage,
            playlist_fetcher=FakePlaylistFetcher(tracks),
            audio_downloader=FakeDownloaderRaises("Network timeout"),
            audio_enricher=FakeEnricher(),
            song_fetcher=FakeSongFetcher(),
            album_fetcher=FakeAlbumFetcher(),
        )

        assert len(results) == 1
        assert results[0]["status"] == "error"
        assert "Network timeout" in results[0]["error_message"]

    def test_wipe_flag(self):
        """Should re-process cached tracks when wipe=True (skip dedup)."""
        tracks = [_make_track("v1", "Song A", "Art A")]
        existing = {"v1": {"videoId": "v1", "title": "Old Song", "genres": ["Rock"]}}
        storage = FakeStorage(existing_tracks=existing)
        downloader = FakeDownloader()
        enricher = FakeEnricher()

        results = process_playlist(
            "PL_WIPE",
            owner="tester",
            wipe=True,
            storage_port=storage,
            playlist_fetcher=FakePlaylistFetcher(tracks),
            audio_downloader=downloader,
            audio_enricher=enricher,
            song_fetcher=FakeSongFetcher(),
            album_fetcher=FakeAlbumFetcher(),
        )

        # wipe=True means the track is re-processed even though it was cached
        assert len(results) == 1
        assert len(downloader.calls) == 1
        assert len(enricher.calls) == 1
        # wipe_db should NOT be called (we skip dedup, not wipe DB)
        assert storage.wipe_called is False

    def test_progress_callback_called(self):
        """Should invoke on_progress callback with correct shape."""
        tracks = [_make_track("prog1", "Progress Song")]
        progress_calls: list[dict] = []

        def on_progress(data: dict):
            progress_calls.append(data)

        process_playlist(
            "PL_PROG",
            owner="user",
            on_progress=on_progress,
            storage_port=FakeStorage(),
            playlist_fetcher=FakePlaylistFetcher(tracks),
            audio_downloader=FakeDownloader(),
            audio_enricher=FakeEnricher(),
            song_fetcher=FakeSongFetcher(),
            album_fetcher=FakeAlbumFetcher(),
        )

        assert len(progress_calls) >= 3  # at least: start, processing, finish
        # Verify shape of a progress call
        for call in progress_calls:
            assert "current" in call
            assert "total" in call
            assert "message" in call
            assert "tokens" in call
            assert "cost" in call

    def test_track_without_video_id_skipped(self):
        """Should skip tracks that have no videoId."""
        tracks = [{"title": "No ID Track", "artists": []}]
        downloader = FakeDownloader()

        results = process_playlist(
            "PL_NOID",
            storage_port=FakeStorage(),
            playlist_fetcher=FakePlaylistFetcher(tracks),
            audio_downloader=downloader,
            audio_enricher=FakeEnricher(),
            song_fetcher=FakeSongFetcher(),
            album_fetcher=FakeAlbumFetcher(),
        )

        assert len(results) == 0
        assert len(downloader.calls) == 0

    def test_enrichment_history_saved(self):
        """Should save enrichment history on completion."""
        storage = FakeStorage()
        tracks = [_make_track("hist1", "History Song")]

        process_playlist(
            "PL_HIST",
            owner="historian",
            storage_port=storage,
            playlist_fetcher=FakePlaylistFetcher(tracks),
            audio_downloader=FakeDownloader(),
            audio_enricher=FakeEnricher(),
            song_fetcher=FakeSongFetcher(),
            album_fetcher=FakeAlbumFetcher(),
        )

        assert len(storage._history) == 1
        assert storage._history[0]["playlist_id"] == "PL_HIST"
        assert storage._history[0]["owner"] == "historian"
        assert storage._history[0]["status"] == "completed"

    def test_token_tracking_from_enricher(self):
        """Should accumulate token usage from enricher results."""
        tracks = [_make_track("tok1"), _make_track("tok2")]
        progress_calls: list[dict] = []

        process_playlist(
            "PL_TOK",
            on_progress=lambda d: progress_calls.append(d),
            storage_port=FakeStorage(),
            playlist_fetcher=FakePlaylistFetcher(tracks),
            audio_downloader=FakeDownloader(),
            audio_enricher=FakeEnricher({
                "genres": ["Jazz"],
                "moods": ["Chill"],
                "instruments": ["Piano"],
                "bpm": 90,
                "usage_metadata": {"prompt_tokens": 500, "candidates_tokens": 200},
            }),
            song_fetcher=FakeSongFetcher(),
            album_fetcher=FakeAlbumFetcher(),
        )

        # Final progress call should reflect accumulated tokens
        final = progress_calls[-1]
        assert final["tokens"] == (500 + 200) * 2  # 2 tracks × 700 tokens each
