"""I/O abstraction protocols for Song Shake.

Defines Protocol classes for external dependencies so business logic can be
tested without real infrastructure. Production code uses real implementations;
tests pass mock/fake implementations.
"""

from typing import Protocol


class StoragePort(Protocol):
    """Abstract storage operations for songs, tracks, and enrichment history."""

    def wipe_db(self) -> None: ...

    def save_track(self, track_data: dict) -> None: ...

    def get_all_tracks(self, owner: str) -> list[dict]: ...

    def get_track_by_id(self, video_id: str) -> dict | None: ...

    def get_tags(self, owner: str) -> list[dict]: ...

    def get_failed_tracks(self, owner: str) -> list[dict]: ...

    def delete_tracks(self, owner: str, video_ids: list[str]) -> int: ...

    def save_enrichment_history(
        self, playlist_id: str, owner: str, metadata: dict
    ) -> None: ...

    def get_enrichment_history(self, owner: str) -> dict: ...

    def get_all_history(self) -> dict: ...

    def save_task_state(self, task_id: str, state: dict) -> None: ...

    def get_task_state(self, task_id: str) -> dict | None: ...


class JobStoragePort(Protocol):
    """Abstract job and AI usage storage operations."""

    def create_job(
        self,
        job_id: str,
        job_type: "JobType",
        playlist_id: str,
        owner: str,
        playlist_name: str = "",
    ) -> dict: ...

    def update_job(self, job_id: str, fields: dict) -> None: ...

    def get_job(self, job_id: str) -> dict | None: ...

    def get_active_jobs(self, owner: str | None = None) -> list[dict]: ...

    def get_job_history(self, owner: str | None = None) -> list[dict]: ...

    def get_job_for_playlist(
        self, playlist_id: str, owner: str | None = None
    ) -> dict | None: ...

    def check_and_create_job(
        self,
        playlist_id: str,
        owner: str,
        job_id: str,
        job_type: "JobType",
        playlist_name: str = "",
    ) -> dict | None: ...

    def get_all_active_jobs(self) -> dict: ...

    def get_ai_usage(self, owner: str) -> dict: ...

    def update_ai_usage(
        self,
        owner: str,
        input_tokens_delta: int,
        output_tokens_delta: int,
        cost_delta: float,
    ) -> dict: ...


class TokenStoragePort(Protocol):
    """Abstract Google OAuth token storage per user."""

    def save_google_tokens(self, user_id: str, tokens: dict) -> None: ...

    def get_google_tokens(self, user_id: str) -> dict | None: ...

    def delete_google_tokens(self, user_id: str) -> None: ...


class AudioEnricher(Protocol):
    """Abstract AI enrichment operations.

    Returns dict with genres, moods, instruments, bpm, album, and optionally
    'usage_metadata': {'prompt_tokens': int, 'candidates_tokens': int,
    'search_queries': int}.
    """

    def enrich_by_url(self, video_id: str, title: str, artist: str) -> dict:
        """Enrich a track via YouTube URL analysis."""
        ...


class PlaylistFetcher(Protocol):
    """Abstract playlist fetching operations."""

    def get_tracks(self, playlist_id: str) -> list[dict]:
        """Fetch tracks from a playlist."""
        ...

    def get_title(self, playlist_id: str) -> str:
        """Get a playlist's title."""
        ...


class AlbumFetcher(Protocol):
    """Abstract album metadata fetching (unauthenticated)."""

    def get_album(self, browse_id: str) -> dict:
        """Fetch album metadata including year, artists, track count."""
        ...


class SongFetcher(Protocol):
    """Abstract song metadata fetching (unauthenticated)."""

    def get_song(self, video_id: str) -> dict:
        """Fetch song details including musicVideoType."""
        ...

    def search_playable_alternative(
        self, title: str, artist: str
    ) -> str | None:
        """Find a playable videoId for a song when original is UNPLAYABLE."""
        ...
