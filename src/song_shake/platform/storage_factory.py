"""Storage backend factory — selects TinyDB or Firestore based on env var.

Usage in FastAPI routes::

    from song_shake.platform.storage_factory import (
        get_songs_storage, get_jobs_storage, get_token_storage,
    )

    @router.get("/songs")
    def list_songs(storage: StoragePort = Depends(get_songs_storage)):
        return storage.get_all_tracks(owner)  
"""

import os
from functools import lru_cache

from song_shake.platform.protocols import (
    JobStoragePort,
    StoragePort,
    TokenStoragePort,
)
from song_shake.features.vibing.storage import VibingStoragePort


@lru_cache(maxsize=1)
def _backend() -> str:
    """Read the storage backend once and cache it for the process lifetime."""
    return os.getenv("STORAGE_BACKEND", "tinydb")


def get_songs_storage() -> StoragePort:
    """Return a StoragePort adapter for the configured backend."""
    if _backend() == "firestore":
        from song_shake.platform.firestore_adapter import FirestoreSongsAdapter

        return FirestoreSongsAdapter()

    from song_shake.features.enrichment.storage_adapter import TinyDBStorageAdapter

    return TinyDBStorageAdapter()


def get_jobs_storage() -> JobStoragePort:
    """Return a JobStoragePort adapter for the configured backend."""
    if _backend() == "firestore":
        from song_shake.platform.firestore_adapter import FirestoreJobsAdapter

        return FirestoreJobsAdapter()

    from song_shake.platform.tinydb_jobs_adapter import TinyDBJobsAdapter

    return TinyDBJobsAdapter()


def get_token_storage() -> TokenStoragePort:
    """Return a TokenStoragePort adapter for the configured backend."""
    if _backend() == "firestore":
        from song_shake.platform.firestore_adapter import FirestoreTokenAdapter

        return FirestoreTokenAdapter()

    from song_shake.platform.tinydb_token_adapter import TinyDBTokenAdapter

    return TinyDBTokenAdapter()


def get_vibing_storage() -> VibingStoragePort:
    """Return a VibingStoragePort adapter.

    Vibing requires Firestore because it reads enriched track data from
    the global ``tracks`` collection.
    """
    if _backend() == "firestore":
        from song_shake.features.vibing.storage import FirestoreVibingAdapter

        return FirestoreVibingAdapter()

    raise NotImplementedError(
        "Vibing feature requires Firestore backend. "
        "Set STORAGE_BACKEND=firestore in your .env file."
    )
