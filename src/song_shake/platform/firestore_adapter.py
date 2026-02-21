"""Firestore adapter implementations for Song Shake storage ports.

Uses firebase-admin SDK. Each adapter maps to a Protocol:
  - FirestoreSongsAdapter  → StoragePort
  - FirestoreJobsAdapter   → JobStoragePort
  - FirestoreTokenAdapter  → TokenStoragePort

All adapters talk to Firestore server-side (admin SDK bypasses security rules).
The firebase-admin SDK must be initialised before using these adapters — this
happens in storage_factory.py via lazy initialisation on first use.
"""

import time as _time
from datetime import datetime, timezone
from functools import lru_cache

from google.cloud.firestore_v1.base_query import FieldFilter

from song_shake.platform.logging_config import get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def _firestore_client():
    """Lazy-init firebase-admin and return the Firestore client.

    Caches the client so firebase_admin.initialize_app() is called at most once.
    """
    import firebase_admin
    from firebase_admin import credentials, firestore

    if not firebase_admin._apps:
        firebase_admin.initialize_app()
    return firestore.client()


# ---------------------------------------------------------------------------
# Songs / Tracks / History / Task State
# ---------------------------------------------------------------------------


# Per-owner TTL cache for get_all_tracks to prevent repeated Firestore reads.
# Key: owner str → (monotonic_timestamp, list[dict])
_tracks_cache: dict[str, tuple[float, list[dict]]] = {}
_TRACKS_CACHE_TTL = 60  # seconds


def _invalidate_tracks_cache(owner: str | None = None) -> None:
    """Clear the tracks cache for a specific owner or all owners."""
    if owner is None:
        _tracks_cache.clear()
    else:
        _tracks_cache.pop(owner, None)


class FirestoreSongsAdapter:
    """StoragePort implementation backed by Firestore."""

    def __init__(self):
        self._db = _firestore_client()

    # --- tracks ---

    def save_track(self, track_data: dict) -> None:
        video_id = track_data.get("videoId")
        if not video_id:
            return
        owner = track_data.get("owner", "local")

        # Global catalog (de-duplicated by videoId)
        global_data = {k: v for k, v in track_data.items() if k != "owner"}
        self._db.collection("tracks").document(video_id).set(global_data, merge=True)

        # Ownership link
        self._db.collection("track_owners").document(f"{owner}_{video_id}").set(
            {"owner": owner, "videoId": video_id}
        )

        _invalidate_tracks_cache(owner)

    def get_all_tracks(self, owner: str) -> list[dict]:
        # Check TTL cache first
        now = _time.monotonic()
        if owner in _tracks_cache:
            cached_at, cached_data = _tracks_cache[owner]
            if now - cached_at < _TRACKS_CACHE_TTL:
                return cached_data

        # Find all videoIds owned by this user
        owner_refs = (
            self._db.collection("track_owners")
            .where(filter=FieldFilter("owner", "==", owner))
            .stream()
        )
        video_ids = [doc.to_dict()["videoId"] for doc in owner_refs]

        if not video_ids:
            _tracks_cache[owner] = (now, [])
            return []

        # Fetch tracks in batches of 30 (Firestore `in` limit)
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
                t["owner"] = owner
                tracks.append(t)

        _tracks_cache[owner] = (now, tracks)
        return tracks

    def get_track_by_id(self, video_id: str) -> dict | None:
        doc = self._db.collection("tracks").document(video_id).get()
        return doc.to_dict() if doc.exists else None

    def get_tags(self, owner: str) -> list[dict]:
        tracks = self.get_all_tracks(owner)
        tag_counts: dict[tuple[str, str], int] = {}

        for t in tracks:
            status = t.get("status", "error")
            status_tag = "Success" if status == "success" else "Failed"
            key = (status_tag, "status")
            tag_counts[key] = tag_counts.get(key, 0) + 1

            for genre in t.get("genres", []):
                key = (genre, "genre")
                tag_counts[key] = tag_counts.get(key, 0) + 1
            for mood in t.get("moods", []):
                key = (mood, "mood")
                tag_counts[key] = tag_counts.get(key, 0) + 1
            for instr in t.get("instruments", []):
                key = (instr, "instrument")
                tag_counts[key] = tag_counts.get(key, 0) + 1

        return sorted(
            [{"name": k[0], "type": k[1], "count": v} for k, v in tag_counts.items()],
            key=lambda x: (-x["count"], x["name"]),
        )

    def get_failed_tracks(self, owner: str) -> list[dict]:
        tracks = self.get_all_tracks(owner)
        return [t for t in tracks if t.get("status") == "error"]

    def delete_tracks(self, owner: str, video_ids: list[str]) -> int:
        """Delete tracks owned by this user.

        1. Delete track_owners/{owner}_{vid} for each video_id.
        2. If no other owners reference the track, delete tracks/{vid} too.

        Returns the count of ownership links removed.
        """
        if not video_ids:
            return 0

        deleted = 0
        batch = self._db.batch()
        batch_count = 0

        # Phase 1: Delete ownership links and collect orphan candidates
        orphan_candidates: list[str] = []
        for vid in video_ids:
            doc_id = f"{owner}_{vid}"
            ref = self._db.collection("track_owners").document(doc_id)
            doc = ref.get()
            if doc.exists:
                batch.delete(ref)
                batch_count += 1
                deleted += 1
                orphan_candidates.append(vid)

            # Firestore batch limit is 500
            if batch_count >= 500:
                batch.commit()
                batch = self._db.batch()
                batch_count = 0

        if batch_count > 0:
            batch.commit()

        # Phase 2: Delete orphaned tracks (no remaining owners)
        if orphan_candidates:
            orphan_batch = self._db.batch()
            orphan_count = 0
            for vid in orphan_candidates:
                remaining = list(
                    self._db.collection("track_owners")
                    .where(filter=FieldFilter("videoId", "==", vid))
                    .limit(1)
                    .stream()
                )
                if not remaining:
                    orphan_batch.delete(
                        self._db.collection("tracks").document(vid)
                    )
                    orphan_count += 1
                    if orphan_count >= 500:
                        orphan_batch.commit()
                        orphan_batch = self._db.batch()
                        orphan_count = 0

            if orphan_count > 0:
                orphan_batch.commit()

        logger.info(
            "tracks_deleted",
            owner=owner,
            requested=len(video_ids),
            deleted=deleted,
        )
        _invalidate_tracks_cache(owner)
        return deleted

    def get_all_tracks_with_tags(
        self, owner: str
    ) -> tuple[list[dict], list[dict]]:
        """Fetch all tracks and compute tag counts in a single read pass.

        Returns (tracks, tags) — avoids duplicate get_all_tracks() call
        that get_tags() would normally make.
        """
        tracks = self.get_all_tracks(owner)

        tag_counts: dict[tuple[str, str], int] = {}
        for t in tracks:
            status = t.get("status", "error")
            status_tag = "Success" if status == "success" else "Failed"
            key = (status_tag, "status")
            tag_counts[key] = tag_counts.get(key, 0) + 1

            for genre in t.get("genres", []):
                key = (genre, "genre")
                tag_counts[key] = tag_counts.get(key, 0) + 1
            for mood in t.get("moods", []):
                key = (mood, "mood")
                tag_counts[key] = tag_counts.get(key, 0) + 1
            for instr in t.get("instruments", []):
                key = (instr, "instrument")
                tag_counts[key] = tag_counts.get(key, 0) + 1

        tags = sorted(
            [
                {"name": k[0], "type": k[1], "count": v}
                for k, v in tag_counts.items()
            ],
            key=lambda x: (-x["count"], x["name"]),
        )
        return tracks, tags

    # --- enrichment history ---

    def save_enrichment_history(
        self, playlist_id: str, owner: str, metadata: dict
    ) -> None:
        doc_id = f"{owner}_{playlist_id}"
        record = {
            "playlistId": playlist_id,
            "owner": owner,
            "last_processed": metadata.get("timestamp"),
            "item_count": metadata.get("item_count", 0),
            "status": metadata.get("status", "completed"),
        }
        if "error" in metadata:
            record["error"] = metadata["error"]
        self._db.collection("enrichment_history").document(doc_id).set(
            record, merge=True
        )

    def get_enrichment_history(self, owner: str) -> dict:
        docs = (
            self._db.collection("enrichment_history")
            .where(filter=FieldFilter("owner", "==", owner))
            .stream()
        )
        result = {}
        for doc in docs:
            d = doc.to_dict()
            # Backward compat: legacy docs stored 'timestamp' instead of 'last_processed'
            if "last_processed" not in d and "timestamp" in d:
                d["last_processed"] = d["timestamp"]
            result[d["playlistId"]] = d
        return result

    def get_all_history(self) -> dict:
        docs = self._db.collection("enrichment_history").stream()
        result: dict = {}
        for doc in docs:
            d = doc.to_dict()
            # Backward compat: legacy docs stored 'timestamp' instead of 'last_processed'
            if "last_processed" not in d and "timestamp" in d:
                d["last_processed"] = d["timestamp"]
            result[d["playlistId"]] = d
        return result

    # --- task state ---

    def save_task_state(self, task_id: str, state: dict) -> None:
        record = {"task_id": task_id, **state}
        self._db.collection("task_states").document(task_id).set(record, merge=True)

    def get_task_state(self, task_id: str) -> dict | None:
        doc = self._db.collection("task_states").document(task_id).get()
        return doc.to_dict() if doc.exists else None

    # --- wipe ---

    def wipe_db(self) -> None:
        """Delete all documents in all collections.

        WARNING: destructive. Used for testing and development only.
        """
        for coll_name in ["tracks", "track_owners", "enrichment_history", "task_states"]:
            docs = self._db.collection(coll_name).stream()
            for doc in docs:
                doc.reference.delete()
        _invalidate_tracks_cache()


# ---------------------------------------------------------------------------
# Jobs / AI Usage
# ---------------------------------------------------------------------------


class FirestoreJobsAdapter:
    """JobStoragePort implementation backed by Firestore."""

    def __init__(self):
        self._db = _firestore_client()

    def create_job(
        self,
        job_id: str,
        job_type,
        playlist_id: str,
        owner: str,
        playlist_name: str = "",
    ) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        record = {
            "id": job_id,
            "type": job_type.value if hasattr(job_type, "value") else str(job_type),
            "playlist_id": playlist_id,
            "playlist_name": playlist_name,
            "owner": owner,
            "status": "pending",
            "total": 0,
            "current": 0,
            "message": "Initializing…",
            "errors": [],
            "ai_usage": {"input_tokens": 0, "output_tokens": 0, "cost": 0.0},
            "created_at": now,
            "updated_at": now,
        }
        self._db.collection("jobs").document(job_id).set(record)
        return record

    def update_job(self, job_id: str, fields: dict) -> None:
        fields["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._db.collection("jobs").document(job_id).update(fields)

    def get_job(self, job_id: str) -> dict | None:
        doc = self._db.collection("jobs").document(job_id).get()
        return doc.to_dict() if doc.exists else None

    def get_active_jobs(self, owner: str | None = None) -> list[dict]:
        query = self._db.collection("jobs").where(filter=FieldFilter("status", "in", ["pending", "running"]))
        if owner:
            query = query.where(filter=FieldFilter("owner", "==", owner))
        return [doc.to_dict() for doc in query.stream()]

    def get_job_history(self, owner: str | None = None) -> list[dict]:
        terminal = ["completed", "error", "cancelled"]
        query = self._db.collection("jobs").where(filter=FieldFilter("status", "in", terminal))
        if owner:
            query = query.where(filter=FieldFilter("owner", "==", owner))
        results = [doc.to_dict() for doc in query.stream()]
        results.sort(key=lambda j: j.get("updated_at", ""), reverse=True)
        return results

    def get_job_for_playlist(
        self, playlist_id: str, owner: str | None = None
    ) -> dict | None:
        query = (
            self._db.collection("jobs")
            .where(filter=FieldFilter("playlist_id", "==", playlist_id))
            .where(filter=FieldFilter("status", "in", ["pending", "running"]))
        )
        if owner:
            query = query.where(filter=FieldFilter("owner", "==", owner))
        docs = list(query.stream())
        return docs[0].to_dict() if docs else None

    def check_and_create_job(
        self,
        playlist_id: str,
        owner: str,
        job_id: str,
        job_type,
        playlist_name: str = "",
    ) -> dict | None:
        """Atomically check for existing active job and create if none exists.

        Uses a Firestore transaction for atomicity.
        """
        from google.cloud.firestore_v1 import transactional

        transaction = self._db.transaction()

        @transactional
        def _check_and_create(txn):
            # Check for existing active job
            query = (
                self._db.collection("jobs")
                .where(filter=FieldFilter("playlist_id", "==", playlist_id))
                .where(filter=FieldFilter("owner", "==", owner))
                .where(filter=FieldFilter("status", "in", ["pending", "running"]))
            )
            existing = list(query.stream(transaction=txn))
            if existing:
                return None

            now = datetime.now(timezone.utc).isoformat()
            record = {
                "id": job_id,
                "type": job_type.value if hasattr(job_type, "value") else str(job_type),
                "playlist_id": playlist_id,
                "playlist_name": playlist_name,
                "owner": owner,
                "status": "pending",
                "total": 0,
                "current": 0,
                "message": "Initializing…",
                "errors": [],
                "ai_usage": {"input_tokens": 0, "output_tokens": 0, "cost": 0.0},
                "created_at": now,
                "updated_at": now,
            }
            doc_ref = self._db.collection("jobs").document(job_id)
            txn.set(doc_ref, record)
            return record

        return _check_and_create(transaction)

    def get_all_active_jobs(self) -> dict:
        jobs = self.get_active_jobs()
        return {j["playlist_id"]: j for j in jobs}

    def get_ai_usage(self, owner: str) -> dict:
        doc = self._db.collection("ai_usage").document(owner).get()
        if doc.exists:
            return doc.to_dict()
        record = {"owner": owner, "input_tokens": 0, "output_tokens": 0, "cost": 0.0}
        self._db.collection("ai_usage").document(owner).set(record)
        return record

    def update_ai_usage(
        self,
        owner: str,
        input_tokens_delta: int,
        output_tokens_delta: int,
        cost_delta: float,
    ) -> dict:
        from google.cloud.firestore_v1 import Increment

        doc_ref = self._db.collection("ai_usage").document(owner)

        # Atomic increment via Firestore transforms
        doc_ref.set(
            {
                "owner": owner,
                "input_tokens": Increment(input_tokens_delta),
                "output_tokens": Increment(output_tokens_delta),
                "cost": Increment(cost_delta),
            },
            merge=True,
        )
        return doc_ref.get().to_dict()


# ---------------------------------------------------------------------------
# Token Store
# ---------------------------------------------------------------------------


class FirestoreTokenAdapter:
    """TokenStoragePort implementation backed by Firestore."""

    def __init__(self):
        self._db = _firestore_client()

    def save_google_tokens(self, user_id: str, tokens: dict) -> None:
        record = {**tokens, "user_id": user_id}
        self._db.collection("google_tokens").document(user_id).set(record)
        logger.debug("google_tokens_saved_firestore", user_id=user_id)

    def get_google_tokens(self, user_id: str) -> dict | None:
        doc = self._db.collection("google_tokens").document(user_id).get()
        return doc.to_dict() if doc.exists else None

    def delete_google_tokens(self, user_id: str) -> None:
        self._db.collection("google_tokens").document(user_id).delete()
        logger.info("google_tokens_deleted_firestore", user_id=user_id)
