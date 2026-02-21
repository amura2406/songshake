"""Storage protocol and Firestore adapter for Playlist Vibing.

Handles:
- Vibe playlist CRUD (``vibe_playlists`` collection, scoped by owner)
- ``last_playlisted_at`` write-back to ``track_owners`` collection
- YouTube API quota tracking (``youtube_quota`` collection)
"""

from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Protocol
from uuid import uuid4

from google.cloud.firestore_v1.base_query import FieldFilter

from song_shake.platform.logging_config import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Protocol (I/O abstraction)
# ---------------------------------------------------------------------------


class VibingStoragePort(Protocol):
    """Abstract storage operations for the vibing feature."""

    def save_playlist(self, playlist: dict) -> str:
        """Persist a new vibe playlist. Returns the playlist ID."""
        ...

    def get_playlist(self, playlist_id: str, owner: str) -> dict | None:
        """Fetch a single vibe playlist by ID and owner."""
        ...

    def list_playlists(self, owner: str) -> list[dict]:
        """List all vibe playlists for an owner, newest first."""
        ...

    def update_playlist_status(
        self, playlist_id: str, owner: str, status: str, youtube_playlist_id: str | None = None
    ) -> None:
        """Update playlist status (draft → synced) and optional YouTube ID."""
        ...

    def write_back_last_playlisted(self, owner: str, video_ids: list[str]) -> None:
        """Batch-update ``last_playlisted_at`` for the given videoIds."""
        ...

    def delete_playlist(self, playlist_id: str, owner: str) -> bool:
        """Delete a vibe playlist. Returns True if deleted."""
        ...

    def get_tracks_for_owner(self, owner: str) -> list[dict]:
        """Fetch all music tracks for an owner (isMusic == True)."""
        ...

    def get_youtube_quota(self, owner: str) -> dict:
        """Return today's YouTube API quota usage for an owner (Pacific Time day)."""
        ...

    def increment_youtube_quota(self, owner: str, units: int) -> dict:
        """Atomically increment today's YouTube API quota counter."""
        ...


# ---------------------------------------------------------------------------
# Firestore implementation
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _firestore_client():
    """Lazy-init firebase-admin and return the Firestore client."""
    import firebase_admin
    from firebase_admin import firestore

    if not firebase_admin._apps:
        firebase_admin.initialize_app()
    return firestore.client()


class FirestoreVibingAdapter:
    """VibingStoragePort implementation backed by Firestore."""

    def __init__(self):
        self._db = _firestore_client()

    # --- Playlist CRUD ---

    def save_playlist(self, playlist: dict) -> str:
        playlist_id = playlist.get("id") or str(uuid4())
        playlist["id"] = playlist_id
        self._db.collection("vibe_playlists").document(playlist_id).set(playlist)
        logger.info("vibe_playlist_saved", playlist_id=playlist_id)
        return playlist_id

    def get_playlist(self, playlist_id: str, owner: str) -> dict | None:
        doc = self._db.collection("vibe_playlists").document(playlist_id).get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        if data.get("owner") != owner:
            return None
        return data

    def list_playlists(self, owner: str) -> list[dict]:
        docs = (
            self._db.collection("vibe_playlists")
            .where(filter=FieldFilter("owner", "==", owner))
            .stream()
        )
        results = [doc.to_dict() for doc in docs]
        # Sort in Python to avoid requiring a Firestore composite index
        results.sort(key=lambda p: p.get("created_at", ""), reverse=True)
        return results

    def update_playlist_status(
        self,
        playlist_id: str,
        owner: str,
        status: str,
        youtube_playlist_id: str | None = None,
    ) -> None:
        updates: dict = {
            "status": status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if youtube_playlist_id is not None:
            updates["youtube_playlist_id"] = youtube_playlist_id
        self._db.collection("vibe_playlists").document(playlist_id).update(updates)
        logger.info(
            "vibe_playlist_status_updated",
            playlist_id=playlist_id,
            status=status,
        )

    def delete_playlist(self, playlist_id: str, owner: str) -> bool:
        doc = self._db.collection("vibe_playlists").document(playlist_id).get()
        if not doc.exists:
            return False
        data = doc.to_dict()
        if data.get("owner") != owner:
            return False
        self._db.collection("vibe_playlists").document(playlist_id).delete()
        logger.info("vibe_playlist_deleted", playlist_id=playlist_id)
        return True

    # --- Write-back ---

    def write_back_last_playlisted(self, owner: str, video_ids: list[str]) -> None:
        """Batch-update last_playlisted_at on track_owners documents.

        Uses Firestore batch writes (max 500 per batch).
        Only updates the ``last_playlisted_at`` field via merge — never
        overwrites other fields.
        """
        from google.cloud.firestore_v1 import SERVER_TIMESTAMP

        batch = self._db.batch()
        count = 0

        for video_id in video_ids:
            doc_id = f"{owner}_{video_id}"
            ref = self._db.collection("track_owners").document(doc_id)
            batch.set(ref, {"last_playlisted_at": SERVER_TIMESTAMP}, merge=True)
            count += 1

            # Firestore batch limit is 500 writes
            if count >= 500:
                batch.commit()
                batch = self._db.batch()
                count = 0

        if count > 0:
            batch.commit()

        logger.info(
            "last_playlisted_at_written",
            owner=owner,
            track_count=len(video_ids),
        )

    # --- Track fetching ---

    def get_tracks_for_owner(self, owner: str) -> list[dict]:
        """Fetch all music tracks for an owner.

        Joins track_owners → tracks, filters isMusic == True,
        and merges last_playlisted_at from the ownership doc.
        """
        # 1. Get all owner refs (include last_playlisted_at)
        owner_refs = (
            self._db.collection("track_owners")
            .where(filter=FieldFilter("owner", "==", owner))
            .stream()
        )

        owner_map: dict[str, dict] = {}
        for doc in owner_refs:
            d = doc.to_dict()
            vid = d.get("videoId")
            if vid:
                owner_map[vid] = d

        if not owner_map:
            return []

        video_ids = list(owner_map.keys())

        # 2. Fetch tracks in batches of 30 (Firestore `in` limit)
        tracks = []
        for i in range(0, len(video_ids), 30):
            batch = video_ids[i : i + 30]
            docs = (
                self._db.collection("tracks")
                .where(filter=FieldFilter("videoId", "in", batch))
                .stream()
            )
            for doc in docs:
                t = doc.to_dict()
                vid = t.get("videoId")
                # Only include music tracks
                if not t.get("isMusic", False):
                    continue
                # Merge last_playlisted_at from owner doc
                owner_data = owner_map.get(vid, {})
                t["last_playlisted_at"] = owner_data.get("last_playlisted_at")
                t["owner"] = owner
                tracks.append(t)

        return tracks

    # --- YouTube API Quota ---

    def get_youtube_quota(self, owner: str) -> dict:
        date_pt = _today_pt()
        doc_id = f"{owner}_{date_pt}"
        doc = self._db.collection("youtube_quota").document(doc_id).get()
        if doc.exists:
            return doc.to_dict()
        record = {
            "owner": owner,
            "date": date_pt,
            "units_used": 0,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._db.collection("youtube_quota").document(doc_id).set(record)
        return record

    def increment_youtube_quota(self, owner: str, units: int) -> dict:
        from google.cloud.firestore_v1 import Increment

        date_pt = _today_pt()
        doc_id = f"{owner}_{date_pt}"
        doc_ref = self._db.collection("youtube_quota").document(doc_id)

        doc_ref.set(
            {
                "owner": owner,
                "date": date_pt,
                "units_used": Increment(units),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            merge=True,
        )
        return doc_ref.get().to_dict()


def _today_pt() -> str:
    """Return today's date string in US/Pacific timezone (YYYY-MM-DD)."""
    from zoneinfo import ZoneInfo

    now_pt = datetime.now(ZoneInfo("US/Pacific"))
    return now_pt.strftime("%Y-%m-%d")
