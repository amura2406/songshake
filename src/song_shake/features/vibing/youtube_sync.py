"""YouTube Data API v3 sync — creates playlists and inserts items.

Each API call costs 50 quota units (playlists.insert and playlistItems.insert).
An optional ``on_quota_used`` callback is invoked after each successful call
so the caller can track quota consumption.
"""

import time
from typing import Callable

import requests

from song_shake.platform.logging_config import get_logger

logger = get_logger(__name__)

DATA_API_BASE = "https://www.googleapis.com/youtube/v3"

QUOTA_PER_CALL = 50


def create_youtube_playlist(
    access_token: str,
    title: str,
    video_ids: list[str],
    description: str = "AI-curated playlist by SongShake Playlist Vibing",
    on_quota_used: Callable[[int], None] | None = None,
) -> str:
    """Create a YouTube playlist and insert tracks.

    Args:
        access_token: Valid Google OAuth access token.
        title: Playlist title (from Gemini).
        video_ids: Ordered list of videoIds to insert.
        description: Playlist description.
        on_quota_used: Optional callback invoked with units consumed after each
            successful API call. Used to track quota in Firestore.

    Returns:
        The created YouTube playlist ID.

    Raises:
        RuntimeError: If playlist creation or item insertion fails.
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
    for idx, video_id in enumerate(video_ids):
        insert_resp = requests.post(
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
    )
    return playlist_id
