"""Production AlbumFetcher adapter wrapping unauthenticated YTMusic."""

from ytmusicapi import YTMusic

from song_shake.platform.logging_config import get_logger

logger = get_logger(__name__)


class YTMusicAlbumAdapter:
    """Fetches album metadata via unauthenticated YTMusic."""

    def __init__(self) -> None:
        self._yt = YTMusic()

    def get_album(self, browse_id: str) -> dict:
        """Fetch album metadata including year, artists, track count."""
        try:
            album = self._yt.get_album(browse_id)
            return {
                "name": album.get("title"),
                "year": album.get("year"),
                "artists": album.get("artists", []),
                "trackCount": album.get("trackCount"),
                "type": album.get("type"),
            }
        except Exception as e:
            logger.warning("get_album_failed", browse_id=browse_id, error=str(e))
            return {}
