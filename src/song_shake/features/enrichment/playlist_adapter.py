"""Production PlaylistFetcher adapter wrapping YTMusic playlist operations."""

from ytmusicapi import YTMusic

from song_shake.features.enrichment import playlist
from song_shake.platform.logging_config import get_logger

logger = get_logger(__name__)


class YTMusicPlaylistAdapter:
    """Wraps playlist module functions behind PlaylistFetcher.

    In the web API, ytmusicapi's internal auth (designed for CLI oauth.json)
    doesn't work with web-flow OAuth tokens. The YouTube Data API v3 works
    correctly. This adapter:
      1. Uses Data API (with access_token) as primary for playlist tracks.
      2. Falls back to ytmusicapi's get_playlist only as a last resort.
      3. Falls back to file-based CLI auth when neither yt nor access_token
         is provided.

    Args:
        yt: Optional pre-authenticated YTMusic instance.
        access_token: Google OAuth access token for Data API calls.
    """

    def __init__(
        self, yt: YTMusic | None = None, access_token: str | None = None
    ) -> None:
        self._yt = yt
        self._access_token = access_token

    def get_tracks(self, playlist_id: str) -> list[dict]:
        """Fetch tracks from a YouTube Music playlist."""
        # 1. Primary: Data API with stored access token (works with web OAuth)
        if self._access_token:
            try:
                from song_shake.features.auth import auth
                tracks = auth.get_data_api_tracks(
                    None, playlist_id, access_token=self._access_token
                )
                logger.info(
                    "playlist_tracks_fetched_via_data_api",
                    playlist_id=playlist_id,
                    count=len(tracks),
                )
                return tracks
            except Exception as e:
                logger.warning(
                    "data_api_tracks_failed",
                    playlist_id=playlist_id,
                    error=str(e),
                )

        # 2. Fallback: ytmusicapi (may work with CLI-flow tokens)
        if self._yt is not None:
            try:
                pl = self._yt.get_playlist(playlist_id, limit=None)
                tracks = pl.get("tracks", [])
                logger.info(
                    "playlist_tracks_fetched_via_ytmusic",
                    playlist_id=playlist_id,
                    count=len(tracks),
                )
                return tracks
            except Exception as e:
                logger.warning(
                    "ytmusic_get_playlist_failed",
                    playlist_id=playlist_id,
                    error=str(e),
                )
                return []

        # 3. Last resort: file-based CLI auth
        return playlist.get_tracks(playlist_id)

    def get_title(self, playlist_id: str) -> str:
        """Get a playlist's title."""
        # Data API doesn't have a clean "get title" — use ytmusicapi first
        if self._yt is not None:
            try:
                pl = self._yt.get_playlist(playlist_id, limit=1)
                return pl["title"]
            except Exception as e:
                logger.debug(
                    "ytmusic_get_title_failed",
                    playlist_id=playlist_id,
                    error=str(e),
                )

        # Fallback: Data API snippet for playlist title
        if self._access_token:
            try:
                import requests
                res = requests.get(
                    "https://www.googleapis.com/youtube/v3/playlists",
                    headers={"Authorization": f"Bearer {self._access_token}"},
                    params={"part": "snippet", "id": playlist_id},
                    timeout=10,
                )
                res.raise_for_status()
                items = res.json().get("items", [])
                if items:
                    return items[0]["snippet"]["title"]
            except Exception as e:
                logger.warning(
                    "data_api_get_title_failed",
                    playlist_id=playlist_id,
                    error=str(e),
                )

        # Last resort: file-based CLI auth
        return playlist.get_playlist_title(playlist_id)


