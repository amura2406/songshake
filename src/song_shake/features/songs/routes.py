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


class PaginatedSongsWithTags(BaseModel):
    items: List[Song]
    total: int
    page: int
    pages: int
    tags: List[TagResponse]


class DeleteSongsRequest(BaseModel):
    video_ids: List[str] = Field(..., min_length=1, max_length=500)


class DeleteSongsResponse(BaseModel):
    deleted: int


# --- Pure helpers ---


def _filter_tracks(
    all_tracks: list[dict],
    tags: str | None,
    min_bpm: int | None,
    max_bpm: int | None,
) -> list[dict]:
    """Filter tracks by tags and BPM range (pure function, no I/O)."""
    filtered = []
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

        filtered.append(track)
    return filtered


def _paginate(
    tracks: list[dict], skip: int, limit: int
) -> dict:
    """Paginate a filtered track list (pure function, no I/O)."""
    total = len(tracks)
    page_num = skip // limit if limit else 0
    pages = math.ceil(total / limit) if limit else 1
    return {
        "items": tracks[skip : skip + limit],
        "total": total,
        "page": page_num,
        "pages": pages,
    }


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
    filtered = _filter_tracks(all_tracks, tags, min_bpm, max_bpm)
    result = _paginate(filtered, skip, limit)

    logger.debug("get_songs_result", count=result["total"], page=result["page"], pages=result["pages"])
    return PaginatedSongs(**result)


@router.get("/songs-with-tags", response_model=PaginatedSongsWithTags)
def get_songs_with_tags(
    user: dict = Depends(get_current_user),
    storage: StoragePort = Depends(get_songs_storage),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    tags: Optional[str] = None,
    min_bpm: Optional[int] = Query(default=None, ge=1, le=300),
    max_bpm: Optional[int] = Query(default=None, ge=1, le=300),
):
    """Return paginated songs and tag counts in a single read pass."""
    owner = user["sub"]
    logger.info(
        "get_songs_with_tags_requested",
        owner=owner,
        skip=skip,
        limit=limit,
        tags=tags,
        min_bpm=min_bpm,
        max_bpm=max_bpm,
    )

    # Use combined method if available (Firestore adapter), fall back to
    # separate calls for other backends.
    if hasattr(storage, "get_all_tracks_with_tags"):
        all_tracks, tag_list = storage.get_all_tracks_with_tags(owner=owner)
    else:
        all_tracks = storage.get_all_tracks(owner=owner)
        tag_list = storage.get_tags(owner=owner)

    filtered = _filter_tracks(all_tracks, tags, min_bpm, max_bpm)
    result = _paginate(filtered, skip, limit)

    logger.debug(
        "get_songs_with_tags_result",
        count=result["total"],
        page=result["page"],
        tags_count=len(tag_list),
    )
    return PaginatedSongsWithTags(**result, tags=tag_list)


@router.get("/tags", response_model=List[TagResponse])
def get_tags(
    user: dict = Depends(get_current_user),
    storage: StoragePort = Depends(get_songs_storage),
):
    return storage.get_tags(owner=user["sub"])


@router.delete("/songs", response_model=DeleteSongsResponse)
def delete_songs(
    req: DeleteSongsRequest,
    user: dict = Depends(get_current_user),
    storage: StoragePort = Depends(get_songs_storage),
):
    """Permanently delete songs from the user's library.

    Deletes ownership links and orphaned global track documents.
    """
    owner = user["sub"]
    logger.info(
        "delete_songs_requested",
        owner=owner,
        count=len(req.video_ids),
    )

    deleted = storage.delete_tracks(owner=owner, video_ids=req.video_ids)

    logger.info(
        "delete_songs_completed",
        owner=owner,
        requested=len(req.video_ids),
        deleted=deleted,
    )
    return DeleteSongsResponse(deleted=deleted)
