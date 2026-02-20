"""Background job execution logic.

Wraps ``process_playlist`` and keeps the Job record up-to-date while the
enrichment runs.  Cancellation is achieved via a ``threading.Event``.
"""

import os
import threading
from datetime import datetime, timezone

from song_shake.features.enrichment import enrichment
from song_shake.features.jobs.models import JobStatus
from song_shake.platform.protocols import JobStoragePort
from song_shake.platform.storage_factory import get_jobs_storage
from song_shake.platform.logging_config import get_logger

logger = get_logger(__name__)

# Pricing constants (duplicated from enrichment for cost calculation)
PRICE_INPUT_AUDIO_PER_1M = 1.00
PRICE_OUTPUT_PER_1M = 3.00

# In-memory map of job_id → threading.Event for cancellation
_cancel_events: dict[str, threading.Event] = {}

# In-memory map of job_id → latest state for fast SSE reads
_job_live_state: dict[str, dict] = {}

# In-memory latest AI usage for SSE broadcast (owner → counters)
_ai_usage_live: dict[str, dict] = {}

# Lock protecting all three in-memory dicts above.
# Needed because compound operations (read-modify-write) aren't atomic
# even under Python's GIL when multiple background threads access them.
_live_state_lock = threading.Lock()


def get_cancel_event(job_id: str) -> threading.Event | None:
    """Return the cancellation event for a job, or None if not tracked."""
    with _live_state_lock:
        return _cancel_events.get(job_id)


def get_live_state(job_id: str) -> dict | None:
    """Return the live in-memory state for a job (for SSE)."""
    with _live_state_lock:
        state = _job_live_state.get(job_id)
        return state.copy() if state else None


def get_live_ai_usage(owner: str) -> dict | None:
    """Return the live in-memory AI usage for an owner (for SSE)."""
    with _live_state_lock:
        usage = _ai_usage_live.get(owner)
        return usage.copy() if usage else None


class CancelledError(Exception):
    """Raised when a job is cancelled."""


def run_enrichment_job(
    job_id: str,
    playlist_id: str,
    owner: str,
    api_key: str,
    wipe: bool = False,
    job_store: JobStoragePort | None = None,
    playlist_fetcher=None,
) -> None:
    """Run the enrichment process as a background job.

    Updates the Job record on each progress tick and on
    completion/error/cancellation.

    Args:
        job_store: Optional JobStoragePort adapter. Falls back to factory
            default when not provided (production default).
    """
    if job_store is None:
        job_store = get_jobs_storage()

    cancel_event = threading.Event()
    with _live_state_lock:
        _cancel_events[job_id] = cancel_event

    # Load persisted all-time AI usage as the baseline for live updates
    baseline_usage = job_store.get_ai_usage(owner)
    baseline_tokens_in = baseline_usage.get("input_tokens", 0)
    baseline_tokens_out = baseline_usage.get("output_tokens", 0)
    baseline_cost = baseline_usage.get("cost", 0.0)

    # Initialise live state
    with _live_state_lock:
        _job_live_state[job_id] = {
            "id": job_id,
            "status": JobStatus.RUNNING.value,
            "total": 0,
            "current": 0,
            "message": "Initializing…",
            "errors": [],
            "ai_usage": {"input_tokens": 0, "output_tokens": 0, "cost": 0.0},
        }

        # Ensure live AI usage reflects the DB baseline (don't overwrite
        # if another job already seeded it — it would be equal or larger).
        if owner not in _ai_usage_live:
            _ai_usage_live[owner] = baseline_usage.copy()

    job_errors: list[dict] = []
    job_ai_usage = {"input_tokens": 0, "output_tokens": 0, "cost": 0.0}

    # Track the *previous* tick values so we can compute deltas
    prev_tokens = 0
    prev_cost = 0.0

    def _cancel_check() -> None:
        """Raise CancelledError if the cancel event is set."""
        if cancel_event.is_set():
            raise CancelledError("Job cancelled by user")

    def _on_progress(progress: dict) -> None:
        """Callback from enrichment.process_playlist."""
        nonlocal job_ai_usage, prev_tokens, prev_cost

        current = progress.get("current", 0)
        total = progress.get("total", 0)
        message = progress.get("message", "")
        tokens = progress.get("tokens", 0)
        cost = progress.get("cost", 0.0)
        track_data = progress.get("track_data")

        # Record errors from individual tracks
        if track_data and track_data.get("error_message"):
            error_entry = {
                "track_title": track_data.get("title", ""),
                "track_video_id": track_data.get("videoId", ""),
                "message": track_data["error_message"],
            }
            job_errors.append(error_entry)

        # Track AI usage delta for this tick
        job_ai_usage = {"input_tokens": tokens, "output_tokens": 0, "cost": cost}

        # Compute delta since last tick for additive live update
        delta_tokens = tokens - prev_tokens
        delta_cost = cost - prev_cost
        prev_tokens = tokens
        prev_cost = cost

        # Update live state
        with _live_state_lock:
            _job_live_state[job_id] = {
                "id": job_id,
                "status": JobStatus.RUNNING.value,
                "total": total,
                "current": current,
                "message": message,
                "errors": job_errors.copy(),
                "ai_usage": job_ai_usage.copy(),
            }

            # Additively update the shared live AI usage with this tick's delta.
            # This is safe across concurrent jobs because each adds only its own delta.
            current_live = _ai_usage_live.get(owner, {"input_tokens": 0, "output_tokens": 0, "cost": 0.0})
            _ai_usage_live[owner] = {
                "input_tokens": current_live["input_tokens"] + delta_tokens,
                "output_tokens": current_live["output_tokens"],
                "cost": current_live["cost"] + delta_cost,
            }

        # Persist AI usage deltas to the shared ai_usage collection
        # on every track so the SSE stream picks up changes across
        # Cloud Run instances (SSE may route to a different instance).
        if delta_tokens > 0 or delta_cost > 0:
            try:
                updated = job_store.update_ai_usage(
                    owner, delta_tokens, 0, delta_cost,
                )
                with _live_state_lock:
                    _ai_usage_live[owner] = updated
            except Exception:
                pass  # Best-effort — final update at job end is the source of truth

        # Persist job progress periodically (every 5 tracks or on first/last)
        if current == 0 or current == total or current % 5 == 0:
            job_store.update_job(job_id, {
                "status": JobStatus.RUNNING.value,
                "total": total,
                "current": current,
                "message": message,
                "errors": job_errors.copy(),
                "ai_usage": job_ai_usage.copy(),
            })

    try:
        logger.info(
            "job_started",
            job_id=job_id,
            playlist_id=playlist_id,
            owner=owner,
        )
        job_store.update_job(job_id, {"status": JobStatus.RUNNING.value})

        enrichment.process_playlist(
            playlist_id=playlist_id,
            owner=owner,
            wipe=wipe,
            api_key=api_key,
            on_progress=_on_progress,
            cancel_check=_cancel_check,
            playlist_fetcher=playlist_fetcher,
        )

        final_status = JobStatus.COMPLETED.value
        final_message = "Enrichment complete"

    except CancelledError:
        logger.info("job_cancelled", job_id=job_id)
        final_status = JobStatus.CANCELLED.value
        final_message = "Cancelled by user"

    except Exception as e:
        logger.error("job_failed", job_id=job_id, error=str(e))
        final_status = JobStatus.ERROR.value
        final_message = str(e)
        job_errors.append({"track_title": "", "track_video_id": "", "message": str(e)})

    # --- Finalise ---

    with _live_state_lock:
        _job_live_state[job_id] = {
            **_job_live_state.get(job_id, {}),
            "status": final_status,
            "message": final_message,
            "errors": job_errors.copy(),
            "ai_usage": job_ai_usage.copy(),
        }

    job_store.update_job(job_id, {
        "status": final_status,
        "message": final_message,
        "errors": job_errors,
        "ai_usage": job_ai_usage,
    })

    # AI usage is already persisted incrementally per-track in _on_progress.
    # No final update_ai_usage call needed — it would double-count tokens.

    # Cleanup in-memory cancel event
    with _live_state_lock:
        _cancel_events.pop(job_id, None)


def run_retry_job(
    job_id: str,
    owner: str,
    api_key: str,
    video_ids: list[str] | None = None,
    job_store: JobStoragePort | None = None,
) -> None:
    """Run the retry process as a background job.

    Wraps ``retry_failed_tracks`` with the same lifecycle management
    as ``run_enrichment_job``.
    """
    if job_store is None:
        job_store = get_jobs_storage()

    cancel_event = threading.Event()
    with _live_state_lock:
        _cancel_events[job_id] = cancel_event

    baseline_usage = job_store.get_ai_usage(owner)

    with _live_state_lock:
        _job_live_state[job_id] = {
            "id": job_id,
            "status": JobStatus.RUNNING.value,
            "total": 0,
            "current": 0,
            "message": "Initializing retry…",
            "errors": [],
            "ai_usage": {"input_tokens": 0, "output_tokens": 0, "cost": 0.0},
        }
        if owner not in _ai_usage_live:
            _ai_usage_live[owner] = baseline_usage.copy()

    job_errors: list[dict] = []
    job_ai_usage = {"input_tokens": 0, "output_tokens": 0, "cost": 0.0}
    prev_tokens = 0
    prev_cost = 0.0

    def _cancel_check() -> None:
        if cancel_event.is_set():
            raise CancelledError("Job cancelled by user")

    def _on_progress(progress: dict) -> None:
        nonlocal job_ai_usage, prev_tokens, prev_cost

        current = progress.get("current", 0)
        total = progress.get("total", 0)
        message = progress.get("message", "")
        tokens = progress.get("tokens", 0)
        cost = progress.get("cost", 0.0)
        track_data = progress.get("track_data")

        if track_data and track_data.get("error_message"):
            job_errors.append({
                "track_title": track_data.get("title", ""),
                "track_video_id": track_data.get("videoId", ""),
                "message": track_data["error_message"],
            })

        job_ai_usage = {"input_tokens": tokens, "output_tokens": 0, "cost": cost}

        delta_tokens = tokens - prev_tokens
        delta_cost = cost - prev_cost
        prev_tokens = tokens
        prev_cost = cost

        with _live_state_lock:
            _job_live_state[job_id] = {
                "id": job_id,
                "status": JobStatus.RUNNING.value,
                "total": total,
                "current": current,
                "message": message,
                "errors": job_errors.copy(),
                "ai_usage": job_ai_usage.copy(),
            }

            current_live = _ai_usage_live.get(
                owner, {"input_tokens": 0, "output_tokens": 0, "cost": 0.0}
            )
            _ai_usage_live[owner] = {
                "input_tokens": current_live["input_tokens"] + delta_tokens,
                "output_tokens": current_live["output_tokens"],
                "cost": current_live["cost"] + delta_cost,
            }

        if current == 0 or current == total or current % 5 == 0:
            job_store.update_job(job_id, {
                "status": JobStatus.RUNNING.value,
                "total": total,
                "current": current,
                "message": message,
                "errors": job_errors.copy(),
                "ai_usage": job_ai_usage.copy(),
            })

    try:
        logger.info("retry_job_started", job_id=job_id, owner=owner)
        job_store.update_job(job_id, {"status": JobStatus.RUNNING.value})

        enrichment.retry_failed_tracks(
            owner=owner,
            api_key=api_key,
            on_progress=_on_progress,
            cancel_check=_cancel_check,
            video_ids=video_ids,
            storage_port=get_songs_storage(),
        )

        final_status = JobStatus.COMPLETED.value
        final_message = "Retry complete"

    except CancelledError:
        logger.info("retry_job_cancelled", job_id=job_id)
        final_status = JobStatus.CANCELLED.value
        final_message = "Cancelled by user"

    except Exception as e:
        logger.error("retry_job_failed", job_id=job_id, error=str(e))
        final_status = JobStatus.ERROR.value
        final_message = str(e)
        job_errors.append({"track_title": "", "track_video_id": "", "message": str(e)})

    # --- Finalise ---
    with _live_state_lock:
        _job_live_state[job_id] = {
            **_job_live_state.get(job_id, {}),
            "status": final_status,
            "message": final_message,
            "errors": job_errors.copy(),
            "ai_usage": job_ai_usage.copy(),
        }

    job_store.update_job(job_id, {
        "status": final_status,
        "message": final_message,
        "errors": job_errors,
        "ai_usage": job_ai_usage,
    })

    try:
        tokens_in = job_ai_usage.get("input_tokens", 0)
        cost_total = job_ai_usage.get("cost", 0.0)
        if tokens_in > 0 or cost_total > 0:
            updated = job_store.update_ai_usage(owner, tokens_in, 0, cost_total)
            with _live_state_lock:
                _ai_usage_live[owner] = updated
    except Exception as e:
        logger.error("ai_usage_update_failed", job_id=job_id, error=str(e))

    with _live_state_lock:
        _cancel_events.pop(job_id, None)
