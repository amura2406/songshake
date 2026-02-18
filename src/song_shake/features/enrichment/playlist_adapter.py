"""Production PlaylistFetcher adapter wrapping YTMusic playlist operations."""

from song_shake.features.enrichment import playlist


class YTMusicPlaylistAdapter:
    """Wraps playlist module functions behind PlaylistFetcher."""

    def get_tracks(self, playlist_id: str) -> list[dict]:
        """Fetch tracks from a YouTube Music playlist."""
        return playlist.get_tracks(playlist_id)

    def get_title(self, playlist_id: str) -> str:
        """Get a playlist's title."""
        return playlist.get_playlist_title(playlist_id)
