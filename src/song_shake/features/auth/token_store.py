"""Thread-safe per-user Google OAuth token storage using TinyDB.

Stores Google access/refresh tokens keyed by user ID so multiple users can
be authenticated concurrently. All operations are protected by a
threading.Lock to prevent corruption from FastAPI's thread-pool executor.
"""

import threading

from tinydb import TinyDB, where

from song_shake.platform.logging_config import get_logger

logger = get_logger(__name__)

_DB_PATH = "songs.db"
_TABLE_NAME = "google_tokens"

_lock = threading.Lock()


def _get_table(db: TinyDB | None = None) -> tuple[TinyDB, any]:
    """Return (db_instance, table). Caller must hold _lock."""
    _db = db or TinyDB(_DB_PATH)
    return _db, _db.table(_TABLE_NAME)


def save_google_tokens(user_id: str, tokens: dict, db: TinyDB | None = None) -> None:
    """Upsert Google OAuth tokens for a user.

    Args:
        user_id: Google user/channel ID.
        tokens: Dict containing access_token, refresh_token, expires_at, etc.
        db: Optional TinyDB instance (for testing).
    """
    with _lock:
        _db, table = _get_table(db)
        # Store user_id inside the document for querying
        record = {**tokens, "user_id": user_id}
        existing = table.search(where("user_id") == user_id)
        if existing:
            table.update(record, where("user_id") == user_id)
            logger.debug("google_tokens_updated", user_id=user_id)
        else:
            table.insert(record)
            logger.debug("google_tokens_inserted", user_id=user_id)


def get_google_tokens(user_id: str, db: TinyDB | None = None) -> dict | None:
    """Retrieve Google OAuth tokens for a user.

    Args:
        user_id: Google user/channel ID.
        db: Optional TinyDB instance (for testing).

    Returns:
        Token dict or None if user has no stored tokens.
    """
    with _lock:
        _db, table = _get_table(db)
        results = table.search(where("user_id") == user_id)
        if results:
            return results[0]
        return None


def delete_google_tokens(user_id: str, db: TinyDB | None = None) -> None:
    """Remove Google OAuth tokens for a user (e.g. on logout).

    Args:
        user_id: Google user/channel ID.
        db: Optional TinyDB instance (for testing).
    """
    with _lock:
        _db, table = _get_table(db)
        removed = table.remove(where("user_id") == user_id)
        logger.info("google_tokens_deleted", user_id=user_id, count=len(removed))
