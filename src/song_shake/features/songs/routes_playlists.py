"""Playlist routes for Song Shake API."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from ytmusicapi import YTMusic

from song_shake.features.songs import storage
from song_shake.features.auth import auth
from song_shake.platform.logging_config import get_logger
from song_shake.features.auth.routes import get_ytmusic

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
def get_playlists(yt: YTMusic = Depends(get_ytmusic)):
    # Import here to access shared state — will be replaced with storage in Group 4
    from song_shake.features.enrichment.routes import enrichment_tasks

    try:
        playlists = []
        try:
            playlists = yt.get_library_playlists(limit=50)
        except Exception as e:
            logger.debug("get_library_playlists_failed", error=str(e))
            try:
                logger.info("attempting_data_api_fallback")
                playlists = auth.get_data_api_playlists(yt, limit=50)
            except Exception as e2:
                logger.error("data_api_fallback_failed", error=str(e2))

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

        # Merge with history and active tasks
        try:
            history = storage.get_all_history()
            logger.debug("enrichment_history_keys", keys=list(history.keys()))

            # Map of active playlists: playlist_id -> task_id
            active_playlists = {}
            for tid, tdata in enrichment_tasks.items():
                if tdata.get("status") in ["pending", "running"]:
                    components = tid.rsplit("_", 1)
                    if len(components) == 2:
                        pid = components[0]
                        active_playlists[pid] = tid

            for p in playlists:
                pid = p.get("playlistId")

                if pid in active_playlists:
                    p["is_running"] = True
                    p["active_task_id"] = active_playlists[pid]
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

        return playlists
    except Exception as e:
        logger.error("get_playlists_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
