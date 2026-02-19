"""Production SongFetcher adapter wrapping unauthenticated YTMusic.

Uses ``get_watch_playlist(videoId)`` for rich per-song metadata (artists,
album, year) and ``get_song(videoId)`` for play count / music detection.
"""

from ytmusicapi import YTMusic

from song_shake.platform.logging_config import get_logger

logger = get_logger(__name__)

# Music video type values that indicate recognized music tracks.
MUSIC_VIDEO_TYPES = frozenset({
    "MUSIC_VIDEO_TYPE_ATV",   # Audio Track Video (album track)
    "MUSIC_VIDEO_TYPE_OMV",   # Official Music Video
    "MUSIC_VIDEO_TYPE_UGC",   # User Generated Content (covers, remixes)
    "MUSIC_VIDEO_TYPE_OFFICIAL_SOURCE_MUSIC",
})


def format_play_count(count: int | None) -> str | None:
    """Convert raw play count to human-readable string (e.g. 3.5M, 123K)."""
    if count is None:
        return None
    if count >= 1_000_000_000:
        value = count / 1_000_000_000
        return f"{value:.1f}B".replace(".0B", "B") if value < 100 else f"{int(value)}B"
    if count >= 1_000_000:
        value = count / 1_000_000
        return f"{value:.1f}M".replace(".0M", "M") if value < 100 else f"{int(value)}M"
    if count >= 1_000:
        value = count / 1_000
        return f"{value:.1f}K".replace(".0K", "K") if value < 100 else f"{int(value)}K"
    return str(count)


class YTMusicSongAdapter:
    """Fetches song metadata via unauthenticated YTMusic.

    Combines get_watch_playlist (for artists/album/year) with
    get_song (for play count and music type detection).
    """

    def __init__(self) -> None:
        self._yt = YTMusic()

    def get_song(self, video_id: str) -> dict:
        """Fetch song details combining watch playlist and song endpoint.

        Returns a dict with keys:
            - isMusic: bool
            - artists: list[{name, id}]
            - album: {name, id} | None
            - year: str | None
            - playCount: str | None  (formatted: "3.5M", "123K")
            - thumbnails: list[{url, width, height}]
            - channelId: str
        """
        # 1. Rich metadata from watch playlist (artists, album, year)
        watch_data = self._fetch_watch_playlist(video_id)

        # 2. Play count + music detection from get_song
        song_data = self._fetch_song_details(video_id)

        # Merge: watch playlist provides artists/album/year,
        # get_song provides viewCount and musicVideoType
        artists = watch_data.get("artists") or song_data.get("artists") or []
        album = watch_data.get("album") or song_data.get("album")
        year = watch_data.get("year") or song_data.get("year")
        is_music = song_data.get("isMusic", watch_data.get("isMusic", True))
        play_count = song_data.get("playCount")
        thumbnails = song_data.get("thumbnails") or []
        channel_id = (
            (artists[0]["id"] if artists and artists[0].get("id") else "")
            or song_data.get("channelId", "")
        )

        return {
            "isMusic": is_music,
            "artists": artists,
            "album": album,
            "year": str(year) if year else None,
            "playCount": play_count,
            "thumbnails": thumbnails,
            "channelId": channel_id,
        }

    def _fetch_watch_playlist(self, video_id: str) -> dict:
        """Fetch rich metadata from get_watch_playlist."""
        try:
            result = self._yt.get_watch_playlist(video_id)
            if not result or not result.get("tracks"):
                return {}

            track = result["tracks"][0]
            video_type = track.get("videoType")

            artists = [
                {"name": a.get("name", "Unknown"), "id": a.get("id")}
                for a in track.get("artists", [])
            ]

            raw_album = track.get("album")
            album = (
                {"name": raw_album["name"], "id": raw_album.get("id")}
                if raw_album and raw_album.get("name")
                else None
            )

            return {
                "isMusic": video_type in MUSIC_VIDEO_TYPES if video_type else None,
                "artists": artists,
                "album": album,
                "year": track.get("year"),
            }
        except Exception as e:
            logger.debug("watch_playlist_failed", video_id=video_id, error=str(e))
            return {}

    def _fetch_song_details(self, video_id: str) -> dict:
        """Fetch play count and music type detection from get_song."""
        try:
            result = self._yt.get_song(video_id)
            vd = result.get("videoDetails", {})
            mvt = vd.get("musicVideoType")

            raw_count = vd.get("viewCount")
            play_count = format_play_count(int(raw_count)) if raw_count else None

            author = vd.get("author", "").removesuffix(" - Topic").strip()

            # Extract square album art thumbnails
            raw_thumbs = vd.get("thumbnail", {}).get("thumbnails", [])
            thumbnails = [
                {"url": t["url"], "width": t.get("width"), "height": t.get("height")}
                for t in raw_thumbs if t.get("url")
            ]

            return {
                "isMusic": mvt in MUSIC_VIDEO_TYPES if mvt else False,
                "artists": [{"name": author, "id": vd.get("channelId", "")}] if author else [],
                "album": None,
                "year": None,
                "playCount": play_count,
                "thumbnails": thumbnails,
                "channelId": vd.get("channelId", ""),
            }
        except Exception as e:
            logger.warning("get_song_failed", video_id=video_id, error=str(e))
            return {
                "isMusic": True,
                "artists": [],
                "album": None,
                "year": None,
                "playCount": None,
                "thumbnails": [],
                "channelId": "",
            }
