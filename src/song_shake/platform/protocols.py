"""I/O abstraction protocols for Song Shake.

Defines Protocol classes for external dependencies so business logic can be
tested without real infrastructure. Production code uses real implementations;
tests pass mock/fake implementations.
"""

from typing import Protocol


class StoragePort(Protocol):
    """Abstract storage operations."""

    def save_track(self, track_data: dict) -> None: ...

    def get_all_tracks(self, owner: str) -> list[dict]: ...

    def get_track_by_id(self, video_id: str) -> dict | None: ...

    def get_tags(self, owner: str) -> list[dict]: ...

    def save_enrichment_history(
        self, playlist_id: str, owner: str, metadata: dict
    ) -> None: ...

    def get_enrichment_history(self, owner: str) -> dict: ...


class AudioDownloader(Protocol):
    """Abstract audio download operations."""

    def download(self, video_id: str, output_dir: str) -> str:
        """Download audio for a video and return the file path."""
        ...


class AudioEnricher(Protocol):
    """Abstract AI enrichment operations."""

    def enrich(self, file_path: str, title: str, artist: str) -> dict:
        """Enrich a track with AI-generated metadata. Returns dict with genres, moods, etc."""
        ...


class PlaylistFetcher(Protocol):
    """Abstract playlist fetching operations."""

    def get_tracks(self, playlist_id: str) -> list[dict]:
        """Fetch tracks from a playlist."""
        ...

    def get_title(self, playlist_id: str) -> str:
        """Get a playlist's title."""
        ...
