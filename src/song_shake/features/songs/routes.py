"""Songs and tags routes for Song Shake API."""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import math

from song_shake.features.auth.dependencies import get_current_user
from song_shake.platform.protocols import StoragePort
from song_shake.platform.storage_factory import get_songs_storage
from song_shake.platform.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["songs"])


# --- Models ---

class Song(BaseModel):
    videoId: str
    title: str
    artists: Any  # str (legacy) or list[{name, id}] (new)
    album: Any = None  # str (legacy) or {name, id} (new)
    year: Optional[str] = None
    isMusic: Optional[bool] = None
    success: Optional[bool] = None
    playableVideoId: Optional[str] = None
    thumbnails: List[Dict[str, Any]] = []
    genres: List[str] = []
    moods: List[str] = []
    instruments: List[str] = []
    bpm: Optional[int] = None
    playCount: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    url: Optional[str] = None
    vocalType: Optional[str] = None


class PaginatedSongs(BaseModel):
    items: List[Song]
    total: int
    page: int
    pages: int


class TagResponse(BaseModel):
    name: str
    type: str
    count: int


# --- Routes ---

@router.get("/songs", response_model=PaginatedSongs)
def get_songs(
    user: dict = Depends(get_current_user),
    storage: StoragePort = Depends(get_songs_storage),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    tags: Optional[str] = None,
    min_bpm: Optional[int] = Query(default=None, ge=1, le=300),
    max_bpm: Optional[int] = Query(default=None, ge=1, le=300),
):
    owner = user["sub"]
    logger.info(
        "get_songs_requested",
        owner=owner,
        skip=skip,
        limit=limit,
        tags=tags,
        min_bpm=min_bpm,
        max_bpm=max_bpm,
    )
    all_tracks = storage.get_all_tracks(owner=owner)

    filtered_tracks = []
    for track in all_tracks:
        bpm = track.get("bpm")
        if min_bpm is not None and (bpm is None or bpm < min_bpm):
            continue
        if max_bpm is not None and (bpm is None or bpm > max_bpm):
            continue

        if tags:
            filter_tags = {t.strip() for t in tags.split(",") if t.strip()}
            track_tags = set(
                track.get("genres", [])
                + track.get("moods", [])
                + track.get("instruments", [])
            )
            if track.get("status") == "success":
                track_tags.add("Success")
            else:
                track_tags.add("Failed")

            if not filter_tags.issubset(track_tags):
                continue

        filtered_tracks.append(track)

    total = len(filtered_tracks)
    page_num = skip // limit if limit else 0
    pages = math.ceil(total / limit) if limit else 1

    logger.debug("get_songs_result", count=total, page=page_num, pages=pages)
    return PaginatedSongs(
        items=filtered_tracks[skip : skip + limit],
        total=total,
        page=page_num,
        pages=pages,
    )


@router.get("/tags", response_model=List[TagResponse])
def get_tags(
    user: dict = Depends(get_current_user),
    storage: StoragePort = Depends(get_songs_storage),
):
    return storage.get_tags(owner=user["sub"])
