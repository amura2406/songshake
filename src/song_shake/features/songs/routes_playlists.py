"""Playlist routes for Song Shake API."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from ytmusicapi import YTMusic

from song_shake.features.songs import storage
from song_shake.features.auth import auth
from song_shake.features.auth.dependencies import get_current_user, get_authenticated_ytmusic
from song_shake.features.auth import token_store
from song_shake.features.jobs import storage as job_storage
from song_shake.platform.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["playlists"])


# --- Models ---

class PlaylistResponse(BaseModel):
    playlistId: str
    title: str
    thumbnails: List[Dict[str, Any]]
    count: Optional[Any] = None
    description: Optional[str] = None
    last_processed: Optional[str] = None
    last_status: Optional[str] = None
    is_running: Optional[bool] = False
    active_task_id: Optional[str] = None


# --- Routes ---

@router.get("/playlists", response_model=List[PlaylistResponse])
def get_playlists(user: dict = Depends(get_current_user)):
    logger.info("get_playlists_started", user_id=user["sub"])
    yt = get_authenticated_ytmusic(user)

    # Get access token for Data API calls
    tokens = token_store.get_google_tokens(user["sub"])
    access_token = tokens.get("access_token") if tokens else None

    try:
        playlists = []
        # Primary: YouTube Data API v3 (returns all user playlists reliably)
        try:
            playlists = auth.get_data_api_playlists(yt, limit=50, access_token=access_token)
            logger.info("playlists_fetched_via_data_api", count=len(playlists))
        except Exception as e:
            logger.debug("data_api_playlists_failed", error=str(e))
            # Fallback: ytmusicapi library playlists
            try:
                playlists = yt.get_library_playlists(limit=50)
                logger.info("playlists_fetched_via_ytmusicapi", count=len(playlists))
            except Exception as e2:
                logger.error("ytmusicapi_playlists_also_failed", error=str(e2))

        # Manually add Liked Music if not present
        has_liked = any(
            p.get("playlistId") == "LM" or p.get("title") == "Your Likes"
            for p in playlists
        )

        if not has_liked:
            liked_music = {
                "playlistId": "LM",
                "title": "Liked Music",
                "thumbnails": [
                    {
                        "url": "https://www.gstatic.com/youtube/media/ytm/images/pbg/liked-music-@576.png",
                        "width": 576,
                        "height": 576,
                    }
                ],
                "count": "Auto",
                "description": "Your liked songs",
            }
            playlists.insert(0, liked_music)

        # Merge with history and active jobs
        try:
            history = storage.get_all_history()
            logger.debug("enrichment_history_keys", keys=list(history.keys()))

            # Use the new Job system to find active jobs by playlist_id
            active_jobs = job_storage.get_all_active_jobs()

            for p in playlists:
                pid = p.get("playlistId")

                if pid in active_jobs:
                    p["is_running"] = True
                    p["active_task_id"] = active_jobs[pid]["id"]
                else:
                    p["is_running"] = False
                    p["active_task_id"] = None

                if pid in history:
                    p["last_processed"] = history[pid].get("last_processed")
                    p["last_status"] = history[pid].get("status")
                    logger.debug(
                        "merged_history",
                        playlist_id=pid,
                        last_processed=p["last_processed"],
                    )
        except Exception as e:
            logger.error("merge_history_failed", error=str(e))

        logger.info("get_playlists_success", count=len(playlists))
        return playlists
    except Exception as e:
        logger.error("get_playlists_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch playlists")
