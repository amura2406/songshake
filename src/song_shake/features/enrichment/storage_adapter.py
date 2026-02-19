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
