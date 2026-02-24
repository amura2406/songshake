"""Production StoragePort adapter wrapping songs/storage TinyDB functions."""

from song_shake.features.songs import storage


class TinyDBStorageAdapter:
    """Wraps song_shake.features.songs.storage free functions behind StoragePort.

    Manages its own TinyDB instance internally.
    """

    def __init__(self, db=None):
        self._db = db if db is not None else storage.init_db()

    def wipe_db(self) -> None:
        storage.wipe_db()
        # Re-initialise after wipe so subsequent calls work
        self._db = storage.init_db()

    def save_track(self, track_data: dict) -> None:
        storage.save_track(self._db, track_data)

    def get_all_tracks(self, owner: str) -> list[dict]:
        return storage.get_all_tracks(self._db, owner)

    def get_track_by_id(self, video_id: str) -> dict | None:
        return storage.get_track_by_id(self._db, video_id)

    def get_tags(self, owner: str) -> list[dict]:
        return storage.get_tags(self._db, owner)

    def get_failed_tracks(self, owner: str) -> list[dict]:
        return storage.get_failed_tracks(self._db, owner)

    def save_enrichment_history(
        self, playlist_id: str, owner: str, metadata: dict
    ) -> None:
        storage.save_enrichment_history(playlist_id, owner, metadata, self._db)

    def get_enrichment_history(self, owner: str) -> dict:
        return storage.get_enrichment_history(owner, self._db)

    def get_all_history(self) -> dict:
        return storage.get_all_history(self._db)

    def save_task_state(self, task_id: str, state: dict) -> None:
        storage.save_task_state(task_id, state, self._db)

    def get_task_state(self, task_id: str) -> dict | None:
        return storage.get_task_state(task_id, self._db)

    def delete_tracks(self, owner: str, video_ids: list[str]) -> int:
        # TinyDB dev adapter — simple implementation
        from tinydb import Query

        if not video_ids:
            return 0
        deleted = 0
        with storage._db_lock:
            user_songs = self._db.table("user_songs")
            songs = self._db.table("songs")
            UserSong = Query()
            Song = Query()
            for vid in video_ids:
                removed = user_songs.remove(
                    (UserSong.owner == owner) & (UserSong.videoId == vid)
                )
                deleted += len(removed)
                # Remove orphaned global track
                remaining = user_songs.search(UserSong.videoId == vid)
                if not remaining:
                    songs.remove(Song.videoId == vid)
        return deleted

    def get_tag_counts(self, owner: str) -> dict:
        """Compute tag counts on-the-fly (TinyDB is fast enough for dev)."""
        tracks = self.get_all_tracks(owner)
        counts: dict[str, int] = {"total": len(tracks)}
        for t in tracks:
            status = t.get("status", "error")
            status_key = "status.Success" if status == "success" else "status.Failed"
            counts[status_key] = counts.get(status_key, 0) + 1
            for g in t.get("genres", []):
                counts[f"genres.{g}"] = counts.get(f"genres.{g}", 0) + 1
            for m in t.get("moods", []):
                counts[f"moods.{m}"] = counts.get(f"moods.{m}", 0) + 1
            for i in t.get("instruments", []):
                counts[f"instruments.{i}"] = counts.get(f"instruments.{i}", 0) + 1
        return counts

    def rebuild_tag_counts(self, owner: str) -> dict:
        """For TinyDB, just re-compute (no persistent tag_counts document)."""
        return self.get_tag_counts(owner)

    def get_paginated_tracks(
        self, owner: str, limit: int = 25, start_after: str | None = None
    ) -> tuple[list[dict], str | None]:
        """Cursor-based pagination for TinyDB (dev mode)."""
        all_tracks = sorted(
            self.get_all_tracks(owner),
            key=lambda t: t.get("videoId", ""),
        )
        # Find start index based on cursor
        start_idx = 0
        if start_after:
            for i, t in enumerate(all_tracks):
                if t.get("videoId") == start_after:
                    start_idx = i + 1
                    break

        page = all_tracks[start_idx : start_idx + limit]
        has_next = start_idx + limit < len(all_tracks)
        next_cursor = page[-1]["videoId"] if has_next and page else None
        return page, next_cursor

