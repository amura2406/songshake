"""FastAPI routes for the Playlist Vibing feature.

Endpoints:
    POST /vibing/generate         — Run Phases 1-2 (seed selection + Gemini curation)
    GET  /vibing/playlists        — List all vibe playlists for the user
    GET  /vibing/playlists/{id}   — Get a single playlist with full track details
    POST /vibing/playlists/{id}/approve — Run Phases 3-4 (YouTube sync + write-back)
"""

import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from song_shake.features.auth.dependencies import get_current_user
from song_shake.features.vibing.gemini_adapter import curate_playlist
from song_shake.features.vibing.logic import (
    build_final_playlist,
    extract_artist_string,
    select_seed_track,
)
from song_shake.features.vibing.models import (
    VibePlaylistDetailResponse,
    VibePlaylistResponse,
    VibePlaylistTrack,
    VibeRequest,
)
from song_shake.features.vibing.storage import VibingStoragePort
from song_shake.features.vibing.youtube_sync import create_youtube_playlist
from song_shake.platform.logging_config import get_logger
from song_shake.platform.protocols import JobStoragePort, TokenStoragePort
from song_shake.platform.storage_factory import (
    get_jobs_storage,
    get_token_storage,
    get_vibing_storage,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/vibing", tags=["vibing"])


# ---------------------------------------------------------------------------
# POST /vibing/generate — Phases 1 + 2
# ---------------------------------------------------------------------------


@router.post("/generate", response_model=VibePlaylistResponse)
def generate_vibe_playlist(
    req: VibeRequest,
    user: dict = Depends(get_current_user),
    storage: VibingStoragePort = Depends(get_vibing_storage),
    job_store: JobStoragePort = Depends(get_jobs_storage),
):
    """Generate an AI-curated vibe playlist.

    Phase 1: Fetch tracks from Firestore, select the neglected seed.
    Phase 2: Call Gemini to curate a cohesive playlist.
    """
    owner = user["sub"]
    correlation_id = str(uuid4())[:8]
    start = time.monotonic()

    logger.info(
        "generate_vibe_started",
        operation="generate_vibe",
        correlationId=correlation_id,
        userId=owner,
        track_count=req.track_count,
    )

    # Phase 1: Firestore ingestion + seed selection
    try:
        tracks = storage.get_tracks_for_owner(owner)
    except Exception as exc:
        logger.error(
            "generate_vibe_fetch_failed",
            correlationId=correlation_id,
            error=str(exc),
        )
        raise HTTPException(status_code=500, detail="Failed to fetch tracks from Firestore.")

    if len(tracks) < req.track_count + 1:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Not enough music tracks. Need at least {req.track_count + 1}, "
                f"but found {len(tracks)}."
            ),
        )

    seed, remaining = select_seed_track(tracks)
    seed_title = seed.get("title", "Unknown")
    seed_artist = extract_artist_string(seed)

    logger.info(
        "seed_track_selected",
        correlationId=correlation_id,
        seed_videoId=seed["videoId"],
        seed_title=seed_title,
        seed_artist=seed_artist,
        catalog_size=len(remaining),
    )

    # Phase 2: Gemini curation
    try:
        gemini_result, ai_usage = curate_playlist(seed, remaining, req.track_count)
    except RuntimeError as exc:
        logger.error(
            "generate_vibe_gemini_failed",
            correlationId=correlation_id,
            error=str(exc),
        )
        raise HTTPException(status_code=502, detail=str(exc))

    # Track AI usage in the global counter
    try:
        job_store.update_ai_usage(
            owner,
            ai_usage.get("input_tokens", 0),
            ai_usage.get("output_tokens", 0),
            ai_usage.get("cost", 0.0),
        )
    except Exception as exc:
        logger.warning("ai_usage_update_failed", correlationId=correlation_id, error=str(exc))

    final_ids = build_final_playlist(seed["videoId"], gemini_result.curated_video_ids)

    # Save as draft playlist
    playlist_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    playlist_doc = {
        "id": playlist_id,
        "owner": owner,
        "title": gemini_result.generated_playlist_title,
        "description": gemini_result.description,
        "seed_video_id": seed["videoId"],
        "seed_title": seed_title,
        "seed_artist": seed_artist,
        "video_ids": final_ids,
        "status": "draft",
        "youtube_playlist_id": None,
        "created_at": now,
        "updated_at": now,
    }

    try:
        storage.save_playlist(playlist_doc)
    except Exception as exc:
        logger.error(
            "generate_vibe_save_failed",
            correlationId=correlation_id,
            error=str(exc),
        )
        raise HTTPException(status_code=500, detail="Failed to save playlist.")

    duration_ms = int((time.monotonic() - start) * 1000)
    logger.info(
        "generate_vibe_success",
        operation="generate_vibe",
        correlationId=correlation_id,
        userId=owner,
        playlist_id=playlist_id,
        playlist_title=gemini_result.generated_playlist_title,
        track_count=len(final_ids),
        duration=duration_ms,
    )

    return VibePlaylistResponse(
        id=playlist_id,
        owner=owner,
        title=gemini_result.generated_playlist_title,
        description=gemini_result.description,
        seed_video_id=seed["videoId"],
        seed_title=seed_title,
        seed_artist=seed_artist,
        video_ids=final_ids,
        status="draft",
        youtube_playlist_id=None,
        created_at=now,
        track_count=len(final_ids),
    )


# ---------------------------------------------------------------------------
# GET /vibing/playlists — List all
# ---------------------------------------------------------------------------


@router.get("/playlists", response_model=list[VibePlaylistResponse])
def list_vibe_playlists(
    user: dict = Depends(get_current_user),
    storage: VibingStoragePort = Depends(get_vibing_storage),
):
    """List all vibe playlists for the current user."""
    owner = user["sub"]
    logger.info("list_vibe_playlists", userId=owner)

    playlists = storage.list_playlists(owner)
    return [
        VibePlaylistResponse(
            id=p["id"],
            owner=p["owner"],
            title=p["title"],
            description=p.get("description", ""),
            seed_video_id=p["seed_video_id"],
            seed_title=p.get("seed_title", ""),
            seed_artist=p.get("seed_artist", ""),
            video_ids=p.get("video_ids", []),
            status=p["status"],
            youtube_playlist_id=p.get("youtube_playlist_id"),
            created_at=p["created_at"],
            track_count=len(p.get("video_ids", [])),
        )
        for p in playlists
    ]


# ---------------------------------------------------------------------------
# GET /vibing/playlists/{id} — Detail with tracks
# ---------------------------------------------------------------------------


@router.get("/playlists/{playlist_id}", response_model=VibePlaylistDetailResponse)
def get_vibe_playlist_detail(
    playlist_id: str,
    user: dict = Depends(get_current_user),
    storage: VibingStoragePort = Depends(get_vibing_storage),
):
    """Get a vibe playlist with full track details."""
    owner = user["sub"]
    playlist = storage.get_playlist(playlist_id, owner)
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found.")

    # Fetch full track data for all videoIds
    video_ids = playlist.get("video_ids", [])
    seed_id = playlist.get("seed_video_id", "")

    # Build track detail list by looking up each videoId from the tracks collection
    from song_shake.platform.firestore_adapter import _firestore_client

    from google.cloud.firestore_v1.base_query import FieldFilter as _FieldFilter

    db = _firestore_client()
    tracks_detail: list[VibePlaylistTrack] = []

    # Fetch in batches of 30
    for i in range(0, len(video_ids), 30):
        batch = video_ids[i : i + 30]
        docs = db.collection("tracks").where(filter=_FieldFilter("videoId", "in", batch)).stream()
        track_map = {}
        for doc in docs:
            t = doc.to_dict()
            track_map[t["videoId"]] = t

        for vid in batch:
            t = track_map.get(vid)
            if t:
                tracks_detail.append(
                    VibePlaylistTrack(
                        videoId=t["videoId"],
                        title=t.get("title", ""),
                        artists=t.get("artists", []),
                        album=t.get("album"),
                        year=t.get("year"),
                        genres=t.get("genres", []),
                        moods=t.get("moods", []),
                        bpm=t.get("bpm"),
                        thumbnails=t.get("thumbnails", []),
                        is_seed=(t["videoId"] == seed_id),
                    )
                )
            else:
                tracks_detail.append(
                    VibePlaylistTrack(videoId=vid, title="(unavailable)", is_seed=(vid == seed_id))
                )

    return VibePlaylistDetailResponse(
        id=playlist["id"],
        owner=playlist["owner"],
        title=playlist["title"],
        description=playlist.get("description", ""),
        seed_video_id=seed_id,
        status=playlist["status"],
        youtube_playlist_id=playlist.get("youtube_playlist_id"),
        created_at=playlist["created_at"],
        tracks=tracks_detail,
    )


# ---------------------------------------------------------------------------
# POST /vibing/playlists/{id}/approve — Phases 3 + 4
# ---------------------------------------------------------------------------

YOUTUBE_DAILY_LIMIT = 10_000
YOUTUBE_QUOTA_PER_CALL = 50


def _next_reset_utc() -> str:
    """Return the next midnight Pacific Time as an ISO UTC string."""
    from zoneinfo import ZoneInfo

    pt = ZoneInfo("US/Pacific")
    now_pt = datetime.now(pt)
    tomorrow_pt = now_pt.replace(hour=0, minute=0, second=0, microsecond=0)
    if tomorrow_pt <= now_pt:
        tomorrow_pt += timedelta(days=1)
    return tomorrow_pt.astimezone(timezone.utc).isoformat()


@router.post("/playlists/{playlist_id}/approve")
def approve_vibe_playlist(
    playlist_id: str,
    user: dict = Depends(get_current_user),
    storage: VibingStoragePort = Depends(get_vibing_storage),
    token_store: TokenStoragePort = Depends(get_token_storage),
):
    """Approve a draft playlist: sync to YouTube and write back timestamps.

    Phase 3: Create YouTube playlist + insert items.
    Phase 4: Batch-update ``last_playlisted_at`` on track_owners.
    """
    owner = user["sub"]
    correlation_id = str(uuid4())[:8]
    start = time.monotonic()

    logger.info(
        "approve_vibe_started",
        operation="approve_vibe",
        correlationId=correlation_id,
        userId=owner,
        playlist_id=playlist_id,
    )

    playlist = storage.get_playlist(playlist_id, owner)
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found.")

    if playlist["status"] == "synced":
        raise HTTPException(status_code=400, detail="Playlist already synced.")

    # Pre-check YouTube quota
    video_ids = playlist.get("video_ids", [])
    estimated_cost = YOUTUBE_QUOTA_PER_CALL + len(video_ids) * YOUTUBE_QUOTA_PER_CALL
    quota = storage.get_youtube_quota(owner)
    remaining = YOUTUBE_DAILY_LIMIT - quota.get("units_used", 0)

    if estimated_cost > remaining:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Insufficient YouTube API quota. This sync needs {estimated_cost:,} units "
                f"but only {remaining:,} remain today. Quota resets at midnight Pacific Time."
            ),
        )

    # Get access token for YouTube API
    tokens = token_store.get_google_tokens(owner)
    if not tokens or not tokens.get("access_token"):
        raise HTTPException(
            status_code=401,
            detail="No Google tokens found. Please re-authenticate.",
        )

    # Check if token is expired and try to refresh
    import os

    import requests

    expires_at = tokens.get("expires_at", 0)
    if time.time() >= expires_at:
        refresh_tok = tokens.get("refresh_token")
        if not refresh_tok:
            raise HTTPException(status_code=401, detail="Token expired, no refresh token.")

        client_id = os.getenv("GOOGLE_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        if not client_id or not client_secret:
            raise HTTPException(status_code=401, detail="Missing OAuth credentials for refresh.")

        try:
            resp = requests.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_tok,
                    "grant_type": "refresh_token",
                },
                timeout=10,
            )
            resp.raise_for_status()
            new_tokens = resp.json()
            tokens["access_token"] = new_tokens["access_token"]
            tokens["expires_at"] = int(time.time()) + new_tokens.get("expires_in", 3600)
            token_store.save_google_tokens(owner, tokens)
        except requests.RequestException as exc:
            logger.error("token_refresh_failed", correlationId=correlation_id, error=str(exc))
            raise HTTPException(status_code=401, detail="Token refresh failed.")

    access_token = tokens["access_token"]
    title = playlist["title"]

    # Phase 3: YouTube sync (with quota tracking callback)
    def _on_quota_used(units: int) -> None:
        try:
            storage.increment_youtube_quota(owner, units)
        except Exception as exc:
            logger.warning("quota_increment_failed", correlationId=correlation_id, error=str(exc))

    try:
        yt_playlist_id = create_youtube_playlist(
            access_token, title, video_ids, on_quota_used=_on_quota_used,
        )
    except RuntimeError as exc:
        logger.error(
            "approve_vibe_youtube_failed",
            correlationId=correlation_id,
            error=str(exc),
        )
        raise HTTPException(status_code=502, detail=f"YouTube sync failed: {exc}")

    # Phase 4: Firestore write-back
    try:
        storage.write_back_last_playlisted(owner, video_ids)
    except Exception as exc:
        logger.error(
            "approve_vibe_writeback_failed",
            correlationId=correlation_id,
            error=str(exc),
        )
        # Don't fail the whole operation — YouTube playlist was created.
        # Log the error and continue.

    # Update playlist status
    storage.update_playlist_status(playlist_id, owner, "synced", yt_playlist_id)

    duration_ms = int((time.monotonic() - start) * 1000)
    logger.info(
        "approve_vibe_success",
        operation="approve_vibe",
        correlationId=correlation_id,
        userId=owner,
        playlist_id=playlist_id,
        youtube_playlist_id=yt_playlist_id,
        duration=duration_ms,
    )

    return {
        "status": "synced",
        "youtube_playlist_id": yt_playlist_id,
        "youtube_url": f"https://music.youtube.com/playlist?list={yt_playlist_id}",
    }


# ---------------------------------------------------------------------------
# DELETE /vibing/playlists/{id}
# ---------------------------------------------------------------------------


@router.delete("/playlists/{playlist_id}")
def delete_vibe_playlist(
    playlist_id: str,
    user: dict = Depends(get_current_user),
    storage: VibingStoragePort = Depends(get_vibing_storage),
):
    """Delete a vibe playlist."""
    owner = user["sub"]
    logger.info("delete_vibe_playlist", userId=owner, playlist_id=playlist_id)

    deleted = storage.delete_playlist(playlist_id, owner)
    if not deleted:
        raise HTTPException(status_code=404, detail="Playlist not found.")

    return {"status": "deleted", "id": playlist_id}


# ---------------------------------------------------------------------------
# YouTube API Quota
# ---------------------------------------------------------------------------


@router.get("/quota")
def get_youtube_quota(
    user: dict = Depends(get_current_user),
    storage: VibingStoragePort = Depends(get_vibing_storage),
):
    """Return the current user's YouTube API quota usage for today."""
    owner = user["sub"]
    quota = storage.get_youtube_quota(owner)
    return {
        "units_used": quota.get("units_used", 0),
        "units_limit": YOUTUBE_DAILY_LIMIT,
        "reset_at_utc": _next_reset_utc(),
    }


@router.post("/quota/seed")
def seed_youtube_quota(
    units: int,
    user: dict = Depends(get_current_user),
    storage: VibingStoragePort = Depends(get_vibing_storage),
):
    """Manually add units to today's quota (for historical syncs)."""
    owner = user["sub"]
    result = storage.increment_youtube_quota(owner, units)
    logger.info("youtube_quota_seeded", userId=owner, units=units)
    return {
        "units_used": result.get("units_used", 0),
        "units_limit": YOUTUBE_DAILY_LIMIT,
    }

