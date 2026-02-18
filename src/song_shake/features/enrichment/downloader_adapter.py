"""Production AudioDownloader adapter wrapping yt-dlp download logic."""

from song_shake.features.enrichment.enrichment import download_track


class YtDlpDownloaderAdapter:
    """Wraps the download_track() free function behind AudioDownloader."""

    def download(self, video_id: str, output_dir: str) -> str:
        """Download audio for a video and return the file path."""
        return download_track(video_id, output_dir)
