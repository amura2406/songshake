"""Enrichment routes for Song Shake API."""

import asyncio
import json
import os
from typing import Any, Dict, Optional


from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from song_shake.features.auth.dependencies import get_current_user, get_authenticated_ytmusic
from song_shake.features.enrichment import enrichment
from song_shake.features.enrichment.playlist_adapter import YTMusicPlaylistAdapter
from song_shake.platform.protocols import StoragePort
from song_shake.platform.storage_factory import get_songs_storage
from song_shake.platform.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/enrichment", tags=["enrichment"])

# In-memory state for real-time SSE streaming (fast reads during progress).
# Final state is persisted to storage so it survives restarts.
enrichment_tasks: Dict[str, Dict[str, Any]] = {}

# Module-level storage reference, set during app startup via init_storage().
_storage: StoragePort | None = None


def init_storage(storage: StoragePort) -> None:
    """Set the module-level storage used by background tasks.

    Called once during app startup. Background tasks can't use FastAPI Depends()
    so they need a module-level reference.
    """
    global _storage
    _storage = storage


def _get_storage() -> StoragePort:
    """Return the module-level storage, falling back to factory if not init'd."""
    if _storage is not None:
        return _storage
    return get_songs_storage()


def _persist_task(task_id: str) -> None:
    """Persist the current in-memory task state to storage."""
    if task_id in enrichment_tasks:
        state = {k: v for k, v in enrichment_tasks[task_id].items() if k != "results"}
        _get_storage().save_task_state(task_id, state)


# --- Models ---

class EnrichmentRequest(BaseModel):
    playlist_id: str
    api_key: Optional[str] = None


# --- Background task ---

def process_enrichment(
    task_id: str,
    playlist_id: str,
    owner: str,
    api_key: str,
    playlist_fetcher=None,
):
    """Background task that delegates to the shared enrichment logic."""
    results: list[dict] = []

    def _on_progress(progress: dict):
        enrichment_tasks[task_id]["status"] = "running"
        enrichment_tasks[task_id]["current"] = progress["current"]
        enrichment_tasks[task_id]["total"] = progress["total"]
        enrichment_tasks[task_id]["message"] = progress["message"]
        enrichment_tasks[task_id]["tokens"] = progress.get("tokens", 0)
        enrichment_tasks[task_id]["cost"] = progress.get("cost", 0)
        if progress.get("track_data"):
            results.append(progress["track_data"])
            enrichment_tasks[task_id]["results"] = results

    try:
        logger.info(
            "enrichment_started",
            playlist_id=playlist_id,
            owner=owner,
            task_id=task_id,
        )
        enrichment_tasks[task_id]["status"] = "running"
        enrichment_tasks[task_id]["message"] = "Initializing..."
        enrichment_tasks[task_id]["tokens"] = 0
        enrichment_tasks[task_id]["cost"] = 0

        enrichment.process_playlist(
            playlist_id=playlist_id,
            owner=owner,
            api_key=api_key,
            on_progress=_on_progress,
            playlist_fetcher=playlist_fetcher,
            storage_port=_get_storage(),
        )

        enrichment_tasks[task_id]["status"] = "completed"
        enrichment_tasks[task_id]["message"] = "Enrichment complete"

    except Exception as e:
        logger.error("enrichment_failed", task_id=task_id, error=str(e))
        enrichment_tasks[task_id]["status"] = "error"
        enrichment_tasks[task_id]["message"] = str(e)

    finally:
        _persist_task(task_id)


# --- Routes ---

@router.post("")
def start_enrichment(request: EnrichmentRequest, background_tasks: BackgroundTasks, user: dict = Depends(get_current_user)):

    api_key = (
        request.api_key
        or os.getenv("GOOGLE_API_KEY")
        or os.getenv("GEMINI_API_KEY")
    )
    if not api_key:
        raise HTTPException(status_code=400, detail="API Key required")

    # Build authenticated playlist fetcher from stored OAuth tokens.
    # This is done eagerly (before the background task) so auth errors
    # are raised synchronously and returned to the user.
    try:
        from song_shake.platform.storage_factory import get_token_storage
        token_store = get_token_storage()
        tokens = token_store.get_google_tokens(user["sub"])
        access_token = tokens.get("access_token") if tokens else None
        yt = get_authenticated_ytmusic(user)
        playlist_fetcher = YTMusicPlaylistAdapter(yt=yt, access_token=access_token)
    except HTTPException:
        raise
    except Exception:
        playlist_fetcher = None  # Fall back to file-based auth (CLI)

    task_id = f"{request.playlist_id}_{os.urandom(4).hex()}"
    enrichment_tasks[task_id] = {
        "status": "pending",
        "total": 0,
        "current": 0,
        "message": "Initializing...",
        "results": [],
    }
    _persist_task(task_id)

    background_tasks.add_task(
        process_enrichment, task_id, request.playlist_id, user["sub"], api_key,
        playlist_fetcher=playlist_fetcher,
    )
    return {"task_id": task_id}


@router.get("/status/{task_id}")
def get_enrichment_status(
    task_id: str,
    storage: StoragePort = Depends(get_songs_storage),
):
    # Check in-memory first (active tasks), then fall back to persistent storage
    if task_id in enrichment_tasks:
        return enrichment_tasks[task_id]

    persisted = storage.get_task_state(task_id)
    if persisted:
        return persisted

    raise HTTPException(status_code=404, detail="Task not found")


@router.get("/stream/{task_id}")
async def stream_enrichment_status(task_id: str):
    if task_id not in enrichment_tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    async def event_generator():
        while True:
            if task_id not in enrichment_tasks:
                yield f"event: error\ndata: {json.dumps({'error': 'Task lost'})}\n\n"
                break

            task = enrichment_tasks[task_id]

            data = json.dumps(
                {
                    "status": task["status"],
                    "total": task["total"],
                    "current": task["current"],
                    "message": task["message"],
                    "tokens": task.get("tokens", 0),
                    "cost": task.get("cost", 0),
                }
            )

            yield f"data: {data}\n\n"

            if task["status"] in ["completed", "error"]:
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
