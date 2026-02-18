"""TinyDB storage operations for jobs and all-time AI usage."""

import threading
from datetime import datetime, timezone

from tinydb import TinyDB, Query

from song_shake.features.jobs.models import JobStatus, JobType, TERMINAL_STATUSES

STORAGE_FILE = "songs.db"

# Module-level lock protects all TinyDB operations in the jobs module
# against concurrent access from multiple background threads.
_db_lock = threading.Lock()


def _db(db: TinyDB | None = None) -> TinyDB:
    if db is not None:
        return db
    return TinyDB(STORAGE_FILE)


# ---------------------------------------------------------------------------
# Job CRUD
# ---------------------------------------------------------------------------


def create_job(
    job_id: str,
    job_type: JobType,
    playlist_id: str,
    owner: str,
    playlist_name: str = "",
    db: TinyDB | None = None,
) -> dict:
    """Insert a new job record and return it."""
    with _db_lock:
        now = datetime.now(timezone.utc).isoformat()
        record = {
            "id": job_id,
            "type": job_type.value,
            "playlist_id": playlist_id,
            "playlist_name": playlist_name,
            "owner": owner,
            "status": JobStatus.PENDING.value,
            "total": 0,
            "current": 0,
            "message": "Initializing…",
            "errors": [],
            "ai_usage": {"input_tokens": 0, "output_tokens": 0, "cost": 0.0},
            "created_at": now,
            "updated_at": now,
        }
        _db(db).table("jobs").insert(record)
        return record


def update_job(job_id: str, fields: dict, db: TinyDB | None = None) -> None:
    """Partially update job fields."""
    with _db_lock:
        fields["updated_at"] = datetime.now(timezone.utc).isoformat()
        Job = Query()
        _db(db).table("jobs").update(fields, Job.id == job_id)


def get_job(job_id: str, db: TinyDB | None = None) -> dict | None:
    """Retrieve a single job by id."""
    with _db_lock:
        Job = Query()
        results = _db(db).table("jobs").search(Job.id == job_id)
        return results[0] if results else None


def get_active_jobs(owner: str | None = None, db: TinyDB | None = None) -> list[dict]:
    """Return pending/running jobs, optionally filtered by owner."""
    with _db_lock:
        Job = Query()
        cond = (Job.status == JobStatus.PENDING.value) | (
            Job.status == JobStatus.RUNNING.value
        )
        if owner:
            cond = cond & (Job.owner == owner)
        return _db(db).table("jobs").search(cond)


def get_job_history(owner: str | None = None, db: TinyDB | None = None) -> list[dict]:
    """Return completed/error/cancelled jobs, optionally filtered by owner."""
    with _db_lock:
        Job = Query()
        terminal_values = [s.value for s in TERMINAL_STATUSES]
        cond = Job.status.one_of(terminal_values)
        if owner:
            cond = cond & (Job.owner == owner)
        results = _db(db).table("jobs").search(cond)
        # Most recent first
        results.sort(key=lambda j: j.get("updated_at", ""), reverse=True)
        return results


def get_job_for_playlist(
    playlist_id: str, owner: str | None = None, db: TinyDB | None = None
) -> dict | None:
    """Return the active job for a given playlist, or None."""
    with _db_lock:
        Job = Query()
        cond = (
            (Job.playlist_id == playlist_id)
            & (
                (Job.status == JobStatus.PENDING.value)
                | (Job.status == JobStatus.RUNNING.value)
            )
        )
        if owner:
            cond = cond & (Job.owner == owner)
        results = _db(db).table("jobs").search(cond)
        return results[0] if results else None


def check_and_create_job(
    playlist_id: str,
    owner: str,
    job_id: str,
    job_type: JobType,
    playlist_name: str = "",
    db: TinyDB | None = None,
) -> dict | None:
    """Atomically check for an existing active job and create one if none exists.

    Returns the new job record, or None if an active job already exists.
    This prevents the TOCTOU race between get_job_for_playlist + create_job.
    """
    with _db_lock:
        database = _db(db)
        Job = Query()
        cond = (
            (Job.playlist_id == playlist_id)
            & (
                (Job.status == JobStatus.PENDING.value)
                | (Job.status == JobStatus.RUNNING.value)
            )
            & (Job.owner == owner)
        )
        existing = database.table("jobs").search(cond)
        if existing:
            return None

        now = datetime.now(timezone.utc).isoformat()
        record = {
            "id": job_id,
            "type": job_type.value,
            "playlist_id": playlist_id,
            "playlist_name": playlist_name,
            "owner": owner,
            "status": JobStatus.PENDING.value,
            "total": 0,
            "current": 0,
            "message": "Initializing…",
            "errors": [],
            "ai_usage": {"input_tokens": 0, "output_tokens": 0, "cost": 0.0},
            "created_at": now,
            "updated_at": now,
        }
        database.table("jobs").insert(record)
        return record


def get_all_active_jobs(db: TinyDB | None = None) -> dict:
    """Return a dict mapping playlist_id → job for all active jobs.

    Used by ``routes_playlists`` to annotate playlist cards.
    """
    jobs = get_active_jobs(db=db)
    mapping: dict[str, dict] = {}
    for j in jobs:
        mapping[j["playlist_id"]] = j
    return mapping


# ---------------------------------------------------------------------------
# All-time AI Usage
# ---------------------------------------------------------------------------


def get_ai_usage(owner: str, db: TinyDB | None = None) -> dict:
    """Return all-time AI usage for an owner. Creates record if missing."""
    with _db_lock:
        Usage = Query()
        results = _db(db).table("ai_usage").search(Usage.owner == owner)
        if results:
            return results[0]
        record = {"owner": owner, "input_tokens": 0, "output_tokens": 0, "cost": 0.0}
        _db(db).table("ai_usage").insert(record)
        return record


def update_ai_usage(
    owner: str,
    input_tokens_delta: int,
    output_tokens_delta: int,
    cost_delta: float,
    db: TinyDB | None = None,
) -> dict:
    """Atomically increment all-time AI usage counters and return updated record.

    The entire read-increment-write is performed under the module lock,
    preventing lost updates when multiple jobs finish concurrently.
    """
    with _db_lock:
        database = _db(db)
        Usage = Query()
        table = database.table("ai_usage")
        results = table.search(Usage.owner == owner)

        if results:
            current = results[0]
            updated = {
                "input_tokens": current["input_tokens"] + input_tokens_delta,
                "output_tokens": current["output_tokens"] + output_tokens_delta,
                "cost": current["cost"] + cost_delta,
            }
            table.update(updated, Usage.owner == owner)
            current.update(updated)
            return current

        record = {
            "owner": owner,
            "input_tokens": input_tokens_delta,
            "output_tokens": output_tokens_delta,
            "cost": cost_delta,
        }
        table.insert(record)
        return record
