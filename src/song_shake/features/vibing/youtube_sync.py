"""YouTube Data API v3 sync — creates playlists and inserts items.

Each API call costs 50 quota units (playlists.insert and playlistItems.insert).
An optional ``on_quota_used`` callback is invoked after each successful call
so the caller can track quota consumption.
"""

import time
from dataclasses import dataclass, field
from typing import Callable

import requests

from song_shake.platform.logging_config import get_logger

logger = get_logger(__name__)

DATA_API_BASE = "https://www.googleapis.com/youtube/v3"

QUOTA_PER_CALL = 50

# Retry settings
MAX_RETRIES = 3
INITIAL_BACKOFF_SECONDS = 1.0
BACKOFF_MULTIPLIER = 2.0
RETRYABLE_STATUS_CODES = frozenset({409, 500, 502, 503, 504})


@dataclass
class SyncResult:
    """Result of a YouTube playlist sync operation."""

    playlist_id: str
    inserted: int
    failed_video_ids: list[str] = field(default_factory=list)


def _insert_with_retry(
    headers: dict,
    playlist_id: str,
    video_id: str,
    max_retries: int = MAX_RETRIES,
    initial_backoff: float = INITIAL_BACKOFF_SECONDS,
) -> requests.Response:
    """Insert a single playlist item with exponential backoff on retryable errors.

    Args:
        headers: Authorization headers.
        playlist_id: Target YouTube playlist ID.
        video_id: Video ID to insert.
        max_retries: Maximum number of retry attempts.
        initial_backoff: Initial backoff delay in seconds.

    Returns:
        The successful response, or the last failed response after all retries.
    """
    backoff = initial_backoff

    for attempt in range(max_retries + 1):
        resp = requests.post(
            f"{DATA_API_BASE}/playlistItems",
            headers=headers,
            params={"part": "snippet"},
            json={
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {
                        "kind": "youtube#video",
                        "videoId": video_id,
                    },
                }
            },
            timeout=15,
        )

        if resp.status_code == 200:
            return resp

        if resp.status_code not in RETRYABLE_STATUS_CODES or attempt == max_retries:
            # Non-retryable error, or last attempt exhausted
            return resp

        logger.warning(
            "youtube_insert_retrying",
            video_id=video_id,
            status=resp.status_code,
            attempt=attempt + 1,
            max_retries=max_retries,
            backoff_seconds=backoff,
        )
        time.sleep(backoff)
        backoff *= BACKOFF_MULTIPLIER

    return resp  # pragma: no cover — unreachable but satisfies type checker


def create_youtube_playlist(
    access_token: str,
    title: str,
    video_ids: list[str],
    description: str = "AI-curated playlist by SongShake Playlist Vibing",
    on_quota_used: Callable[[int], None] | None = None,
) -> SyncResult:
    """Create a YouTube playlist and insert tracks.

    Args:
        access_token: Valid Google OAuth access token.
        title: Playlist title (from Gemini).
        video_ids: Ordered list of videoIds to insert.
        description: Playlist description.
        on_quota_used: Optional callback invoked with units consumed after each
            successful API call. Used to track quota in Firestore.

    Returns:
        SyncResult with playlist_id, inserted count, and failed video IDs.

    Raises:
        RuntimeError: If playlist creation fails.
    """
    headers = {"Authorization": f"Bearer {access_token}"}

    # --- Create playlist (50 units) ---
    logger.info("youtube_create_playlist_started", title=title)
    create_resp = requests.post(
        f"{DATA_API_BASE}/playlists",
        headers=headers,
        params={"part": "snippet,status"},
        json={
            "snippet": {
                "title": title,
                "description": description,
            },
            "status": {"privacyStatus": "private"},
        },
        timeout=15,
    )

    if create_resp.status_code != 200:
        logger.error(
            "youtube_create_playlist_failed",
            status=create_resp.status_code,
            body=create_resp.text,
        )
        raise RuntimeError(
            f"YouTube playlist creation failed: {create_resp.status_code} — "
            f"{create_resp.text}"
        )

    playlist_id = create_resp.json()["id"]
    logger.info("youtube_playlist_created", playlist_id=playlist_id)

    if on_quota_used:
        on_quota_used(QUOTA_PER_CALL)

    # --- Insert items (50 units each) ---
    inserted = 0
    failed_video_ids: list[str] = []

    for idx, video_id in enumerate(video_ids):
        insert_resp = _insert_with_retry(headers, playlist_id, video_id)

        if insert_resp.status_code == 200:
            inserted += 1
            if on_quota_used:
                on_quota_used(QUOTA_PER_CALL)
        else:
            logger.warning(
                "youtube_insert_item_failed",
                video_id=video_id,
                status=insert_resp.status_code,
                body=insert_resp.text[:200],
            )
            failed_video_ids.append(video_id)

        if idx < len(video_ids) - 1:
            time.sleep(0.5)

        if (idx + 1) % 10 == 0:
            logger.info(
                "youtube_insert_progress",
                inserted=inserted,
                total=len(video_ids),
            )

    logger.info(
        "youtube_sync_complete",
        playlist_id=playlist_id,
        inserted=inserted,
        total=len(video_ids),
        failed_count=len(failed_video_ids),
    )
    return SyncResult(
        playlist_id=playlist_id,
        inserted=inserted,
        failed_video_ids=failed_video_ids,
    )


def _fetch_existing_video_ids(
    headers: dict,
    playlist_id: str,
) -> set[str]:
    """Fetch all video IDs currently in a YouTube playlist.

    Paginates through ``playlistItems.list`` to collect every videoId.
    """
    existing: set[str] = set()
    page_token: str | None = None

    while True:
        params: dict = {
            "part": "snippet",
            "playlistId": playlist_id,
            "maxResults": 50,
        }
        if page_token:
            params["pageToken"] = page_token

        resp = requests.get(
            f"{DATA_API_BASE}/playlistItems",
            headers=headers,
            params=params,
            timeout=15,
        )

        if resp.status_code != 200:
            logger.error(
                "youtube_fetch_items_failed",
                playlist_id=playlist_id,
                status=resp.status_code,
                body=resp.text[:200],
            )
            raise RuntimeError(
                f"Failed to fetch YouTube playlist items: {resp.status_code}"
            )

        data = resp.json()
        for item in data.get("items", []):
            vid = item.get("snippet", {}).get("resourceId", {}).get("videoId")
            if vid:
                existing.add(vid)

        page_token = data.get("nextPageToken")
        if not page_token:
            break

    logger.info(
        "youtube_existing_items_fetched",
        playlist_id=playlist_id,
        count=len(existing),
    )
    return existing


def complete_youtube_playlist(
    access_token: str,
    playlist_id: str,
    video_ids: list[str],
    on_quota_used: Callable[[int], None] | None = None,
) -> SyncResult:
    """Insert only missing tracks into an existing YouTube playlist.

    Compares the desired ``video_ids`` against what's already in the YouTube
    playlist and inserts only the difference.

    Args:
        access_token: Valid Google OAuth access token.
        playlist_id: Existing YouTube playlist ID.
        video_ids: Full ordered list of desired videoIds.
        on_quota_used: Optional quota tracking callback.

    Returns:
        SyncResult with the playlist_id, count of newly inserted tracks,
        and any video IDs that still failed after retries.
    """
    headers = {"Authorization": f"Bearer {access_token}"}

    # Fetch what's already in the playlist
    existing = _fetch_existing_video_ids(headers, playlist_id)
    missing = [vid for vid in video_ids if vid not in existing]

    logger.info(
        "youtube_complete_started",
        playlist_id=playlist_id,
        total=len(video_ids),
        already_present=len(existing),
        missing=len(missing),
    )

    if not missing:
        logger.info("youtube_complete_nothing_to_do", playlist_id=playlist_id)
        return SyncResult(playlist_id=playlist_id, inserted=0, failed_video_ids=[])

    inserted = 0
    failed_video_ids: list[str] = []

    for idx, video_id in enumerate(missing):
        insert_resp = _insert_with_retry(headers, playlist_id, video_id)

        if insert_resp.status_code == 200:
            inserted += 1
            if on_quota_used:
                on_quota_used(QUOTA_PER_CALL)
        else:
            logger.warning(
                "youtube_complete_item_failed",
                video_id=video_id,
                status=insert_resp.status_code,
                body=insert_resp.text[:200],
            )
            failed_video_ids.append(video_id)

        if idx < len(missing) - 1:
            time.sleep(0.5)

    logger.info(
        "youtube_complete_done",
        playlist_id=playlist_id,
        inserted=inserted,
        still_missing=len(failed_video_ids),
    )
    return SyncResult(
        playlist_id=playlist_id,
        inserted=inserted,
        failed_video_ids=failed_video_ids,
    )
