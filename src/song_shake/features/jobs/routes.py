"""Job management REST endpoints.

Prefix: ``/jobs``
"""

import asyncio
import json
import os
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from song_shake.features.auth.dependencies import get_current_user, get_authenticated_ytmusic
from song_shake.features.enrichment.playlist_adapter import YTMusicPlaylistAdapter
from song_shake.features.jobs import logic
from song_shake.features.jobs.models import (
    AIUsageResponse,
    JobCreateRequest,
    JobResponse,
    JobStatus,
    JobType,
    TERMINAL_STATUSES,
)
from song_shake.platform.protocols import JobStoragePort
from song_shake.platform.storage_factory import get_jobs_storage
from song_shake.platform.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])


# ---------------------------------------------------------------------------
# POST /jobs  — create a new enrichment job
# ---------------------------------------------------------------------------


@router.post("", response_model=JobResponse)
def create_job(
    request: JobCreateRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
    job_store: JobStoragePort = Depends(get_jobs_storage),
):
    api_key = (
        request.api_key
        or os.getenv("GOOGLE_API_KEY")
        or os.getenv("GEMINI_API_KEY")
    )
    if not api_key:
        raise HTTPException(status_code=400, detail="API Key required")

    owner = user["sub"]
    job_id = f"job_{request.playlist_id}_{os.urandom(4).hex()}"

    # Atomic check-and-create prevents TOCTOU race between duplicate check and insert
    job = job_store.check_and_create_job(
        playlist_id=request.playlist_id,
        owner=owner,
        job_id=job_id,
        job_type=JobType.ENRICHMENT,
        playlist_name=request.playlist_name,
    )
    if job is None:
        raise HTTPException(
            status_code=409,
            detail="An active job already exists for this playlist",
        )

    logger.info(
        "job_created",
        job_id=job_id,
        playlist_id=request.playlist_id,
        owner=owner,
    )

    # Build authenticated playlist fetcher from stored OAuth tokens.
    try:
        from song_shake.platform.storage_factory import get_token_storage
        token_store = get_token_storage()
        tokens = token_store.get_google_tokens(owner)
        access_token = tokens.get("access_token") if tokens else None
        yt = get_authenticated_ytmusic(user)
        playlist_fetcher = YTMusicPlaylistAdapter(yt=yt, access_token=access_token)
    except HTTPException:
        raise
    except Exception:
        playlist_fetcher = None

    background_tasks.add_task(
        logic.run_enrichment_job,
        job_id,
        request.playlist_id,
        owner,
        api_key,
        request.wipe,
        playlist_fetcher=playlist_fetcher,
    )

    return job


# ---------------------------------------------------------------------------
# GET /jobs  — list jobs
# ---------------------------------------------------------------------------


@router.get("")
def list_jobs(
    user: dict = Depends(get_current_user),
    job_store: JobStoragePort = Depends(get_jobs_storage),
    status: str | None = None,
):
    owner = user["sub"]
    if status == "active":
        jobs = job_store.get_active_jobs(owner)
        # Enrich with live state
        for j in jobs:
            live = logic.get_live_state(j["id"])
            if live:
                j.update(live)
        return jobs
    if status == "history":
        return job_store.get_job_history(owner)
    # Default: return all active + recent history
    active = job_store.get_active_jobs(owner)
    for j in active:
        live = logic.get_live_state(j["id"])
        if live:
            j.update(live)
    history = job_store.get_job_history(owner)
    return {"active": active, "history": history[:20]}


# ---------------------------------------------------------------------------
# Retry endpoints — MUST be registered BEFORE /{job_id} wildcard routes
# ---------------------------------------------------------------------------


class RetryRequest(BaseModel):
    """Payload for retrying failed tracks."""

    api_key: Optional[str] = None


@router.post("/retry", response_model=JobResponse)
def retry_failed(
    request: RetryRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
    job_store: JobStoragePort = Depends(get_jobs_storage),
):
    """Retry enrichment for all failed tracks."""
    api_key = (
        request.api_key
        or os.getenv("GOOGLE_API_KEY")
        or os.getenv("GEMINI_API_KEY")
    )
    if not api_key:
        raise HTTPException(status_code=400, detail="API Key required")

    owner = user["sub"]
    job_id = f"retry_{owner}_{os.urandom(4).hex()}"

    job = job_store.check_and_create_job(
        playlist_id=f"retry_{owner}",
        owner=owner,
        job_id=job_id,
        job_type=JobType.RETRY,
        playlist_name="Retry Failed Tracks",
    )
    if job is None:
        raise HTTPException(
            status_code=409,
            detail="A retry job is already running",
        )

    logger.info("retry_job_created", job_id=job_id, owner=owner)
    background_tasks.add_task(logic.run_retry_job, job_id, owner, api_key)
    return job


@router.post("/retry/{video_id}", response_model=JobResponse)
def retry_single_track(
    video_id: str,
    request: RetryRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
    job_store: JobStoragePort = Depends(get_jobs_storage),
):
    """Retry enrichment for a single track by videoId."""
    api_key = (
        request.api_key
        or os.getenv("GOOGLE_API_KEY")
        or os.getenv("GEMINI_API_KEY")
    )
    if not api_key:
        raise HTTPException(status_code=400, detail="API Key required")

    owner = user["sub"]
    job_id = f"retry_{video_id}_{os.urandom(4).hex()}"

    job = job_store.check_and_create_job(
        playlist_id=f"retry_{video_id}",
        owner=owner,
        job_id=job_id,
        job_type=JobType.RETRY,
        playlist_name=f"Retry: {video_id}",
    )
    if job is None:
        raise HTTPException(
            status_code=409,
            detail="A retry job for this track is already running",
        )

    logger.info(
        "single_retry_job_created",
        job_id=job_id,
        video_id=video_id,
        owner=owner,
    )
    background_tasks.add_task(
        logic.run_retry_job, job_id, owner, api_key, [video_id]
    )
    return job


# ---------------------------------------------------------------------------
# AI Usage endpoints — MUST be registered BEFORE /{job_id} wildcard routes
# to prevent FastAPI from matching "ai-usage" as a job_id.
# ---------------------------------------------------------------------------


@router.get("/ai-usage/current")
async def get_ai_usage(
    user: dict = Depends(get_current_user),
    job_store: JobStoragePort = Depends(get_jobs_storage),
):
    usage = await asyncio.to_thread(job_store.get_ai_usage, user["sub"])
    return usage


@router.get("/ai-usage/stream")
async def stream_ai_usage(
    user: dict = Depends(get_current_user),
    job_store: JobStoragePort = Depends(get_jobs_storage),
):
    owner = user["sub"]

    async def event_generator():
        last_hash = ""
        while True:
            # Always read from database — on Cloud Run with multiple
            # instances, the SSE connection may be routed to a different
            # instance than the one running the background job, so the
            # in-memory _ai_usage_live dict may be stale.
            live = await asyncio.to_thread(logic.get_live_ai_usage, owner)
            db_usage = await asyncio.to_thread(job_store.get_ai_usage, owner)

            # Use whichever has more tokens (live may be ahead of DB
            # if this happens to be the same instance as the job)
            live_tokens = (live or {}).get("input_tokens", 0)
            db_tokens = db_usage.get("input_tokens", 0)
            usage = live if live_tokens > db_tokens else db_usage

            data = json.dumps(usage, default=str)
            current_hash = data

            # Only send if changed
            if current_hash != last_hash:
                yield f"data: {data}\n\n"
                last_hash = current_hash

            await asyncio.sleep(1.0)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}  — wildcard routes AFTER fixed-path routes
# ---------------------------------------------------------------------------


@router.get("/{job_id}")
def get_job(
    job_id: str,
    user: dict = Depends(get_current_user),
    job_store: JobStoragePort = Depends(get_jobs_storage),
):
    # Live state first (fast reads for active jobs)
    live = logic.get_live_state(job_id)
    if live:
        return live

    persisted = job_store.get_job(job_id)
    if persisted:
        return persisted

    raise HTTPException(status_code=404, detail="Job not found")


# ---------------------------------------------------------------------------
# POST /jobs/{job_id}/cancel
# ---------------------------------------------------------------------------


@router.post("/{job_id}/cancel")
def cancel_job(
    job_id: str,
    user: dict = Depends(get_current_user),
    job_store: JobStoragePort = Depends(get_jobs_storage),
):
    event = logic.get_cancel_event(job_id)
    if event:
        # Normal case: job is running in-memory, signal cancellation
        event.set()
        logger.info("job_cancel_requested", job_id=job_id)
        return {"message": "Cancellation requested", "job_id": job_id}

    # No in-memory cancel event — check DB
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.get("status") in [s.value for s in TERMINAL_STATUSES]:
        raise HTTPException(status_code=409, detail="Job already finished")

    # Zombie job: still "running"/"pending" in DB but has no in-memory
    # process (e.g. server was restarted). Mark it as failed directly.
    job_store.update_job(job_id, {
        "status": JobStatus.ERROR.value,
        "message": "Cancelled (job was orphaned after server restart)",
    })
    logger.info("zombie_job_cancelled", job_id=job_id)
    return {"message": "Orphaned job marked as failed", "job_id": job_id}


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}/stream  — SSE for single job progress
# ---------------------------------------------------------------------------


@router.get("/{job_id}/stream")
async def stream_job(
    job_id: str,
    user: dict = Depends(get_current_user),
    job_store: JobStoragePort = Depends(get_jobs_storage),
):
    # Must exist in live state or DB
    live = await asyncio.to_thread(logic.get_live_state, job_id)
    persisted = await asyncio.to_thread(job_store.get_job, job_id) if not live else None

    if not live and not persisted:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        while True:
            state = await asyncio.to_thread(logic.get_live_state, job_id)
            if not state:
                # Job may have finished and been cleaned from memory
                db_state = await asyncio.to_thread(job_store.get_job, job_id)
                if db_state:
                    # Send final state and close
                    yield f"data: {json.dumps(db_state, default=str)}\n\n"
                break

            yield f"data: {json.dumps(state, default=str)}\n\n"

            if state.get("status") in [s.value for s in TERMINAL_STATUSES]:
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
