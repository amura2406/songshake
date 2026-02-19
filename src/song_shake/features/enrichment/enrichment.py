import os
import json
import uuid
from rich.console import Console
from rich.progress import Progress
from rich.table import Table
import yt_dlp
from google import genai
from google.genai import types
import shutil
from dotenv import load_dotenv
import time
from song_shake.platform.logging_config import get_logger
from song_shake.platform.protocols import (
    AlbumFetcher,
    AudioDownloader,
    AudioEnricher,
    PlaylistFetcher,
    SongFetcher,
    StoragePort,
)

logger = get_logger(__name__)

console = Console()

TEMP_DIR_BASE = "temp_downloads"

# Pricing for Gemini 3 Flash (Preview)
# Input Audio: $1.00 / 1M tokens
# Output: $3.00 / 1M tokens
PRICE_INPUT_AUDIO_PER_1M = 1.00
PRICE_OUTPUT_PER_1M = 3.00

class TokenTracker:
    def __init__(self):
        self.input_tokens = 0
        self.output_tokens = 0
        self.successful = 0
        self.failed = 0
        self.errors = []
    
    def add_usage(self, usage_metadata):
        if not usage_metadata:
            return
        # usage_metadata is likely an object with prompt_token_count, candidates_token_count
        # checking structure...
        p_tokens = getattr(usage_metadata, 'prompt_token_count', 0)
        c_tokens = getattr(usage_metadata, 'candidates_token_count', 0)
        
        self.input_tokens += p_tokens
        self.output_tokens += c_tokens

    def add_usage_from_dict(self, usage_dict: dict) -> None:
        """Update token counts from a plain dict (returned by AudioEnricher adapters)."""
        if not usage_dict:
            return
        self.input_tokens += usage_dict.get("prompt_tokens", 0)
        self.output_tokens += usage_dict.get("candidates_tokens", 0)

    def get_cost(self):
        input_cost = (self.input_tokens / 1_000_000) * PRICE_INPUT_AUDIO_PER_1M
        output_cost = (self.output_tokens / 1_000_000) * PRICE_OUTPUT_PER_1M
        return input_cost + output_cost

    def print_summary(self):
        total_cost = self.get_cost()
        
        table = Table(title="Processing Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")
        
        table.add_row("Successful", str(self.successful))
        table.add_row("Failed", str(self.failed))
        table.add_row("Input Tokens", f"{self.input_tokens:,}")
        table.add_row("Output Tokens", f"{self.output_tokens:,}")
        table.add_row("Est. Cost", f"${total_cost:.6f}")
        
        console.print(table)


def download_track(video_id: str, output_dir: str = TEMP_DIR_BASE) -> str:
    """Download track audio. Returns path to file."""
    os.makedirs(output_dir, exist_ok=True)
    # yt-dlp options to force audio only
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{output_dir}/%(id)s.%(ext)s',
        'quiet': True,
        'overwrites': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '128',
        }],
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_id, download=True)
        # prepares filename with correct extension (mp3)
        filename = ydl.prepare_filename(info)
        # prepare_filename might return .webm or .m4a but postprocessor changes it to .mp3
        # We need to predict the final filename
        pre, _ = os.path.splitext(filename)
        final_filename = f"{pre}.mp3"
        return final_filename

def enrich_track(client: genai.Client, file_path: str, title: str, artist: str, tracker: TokenTracker) -> dict:
    """Upload to Gemini and get metadata."""
    try:
        # Upload file (Gemini File API)
        # 'file' argument is correct for updated SDK
        f = client.files.upload(file=file_path)
        
        # Wait for processing state if video? Audio usually instant-ish.
        # But good practice to check state if applicable. 
        # For small audio context it's usually Active immediately.
        
        prompt = f"""
        Analyze this audio track.
        Title: {title}
        Artist: {artist}
        
        Provide a JSON object with:
        - genres: list of strings (e.g. "Pop", "Rock", "Indie"). IMPORTANT: Use consistent and standard capitalization. For hyphenated genres, capitalize only the first word (e.g., "Synth-pop", not "Synth-Pop" or "Synthpop").
        - moods: list of strings (e.g. "Happy", "Sad", "Energetic"). Capitalize the first letter.
        - bpm: integer representing the BPM count
        - instruments: list of strings representing the main instruments played (e.g. "Bass", "Guitar", "Piano")
        
        Only return the JSON.
        """
        
        response = client.models.generate_content(
            model='gemini-3-flash-preview', # Using Gemini 3 Flash Preview as requested
            contents=[f, prompt],
            config=types.GenerateContentConfig(
                response_mime_type='application/json'
            )
        )
        
        # Track usage
        if response.usage_metadata:
            tracker.add_usage(response.usage_metadata)
            
            # Log usage for this specific call
            p_tokens = response.usage_metadata.prompt_token_count
            c_tokens = response.usage_metadata.candidates_token_count
            cost = (p_tokens / 1e6 * PRICE_INPUT_AUDIO_PER_1M) + (c_tokens / 1e6 * PRICE_OUTPUT_PER_1M)
            console.print(f"  [dim]Usage: {p_tokens} in / {c_tokens} out (~${cost:.5f})[/dim]")
        
        try:
             data = json.loads(response.text)
             
             # Post-process genres to ensure consistency
             if 'genres' in data and isinstance(data['genres'], list):
                 normalized_genres = []
                 for g in data['genres']:
                     # Force "Synthpop" -> "Synth-pop"
                     if g.lower() == 'synthpop':
                         g = 'Synth-pop'
                     # Capitalize first letter only for hyphenated names (e.g. Synth-Pop -> Synth-pop)
                     elif '-' in g:
                         parts = g.split('-')
                         g = '-'.join([parts[0].capitalize()] + [p.lower() for p in parts[1:]])
                     else:
                         g = g.capitalize()
                     normalized_genres.append(g)
                 data['genres'] = list(set(normalized_genres)) # deduplicate
                 
             return data
        except json.JSONDecodeError as e:
             logger.warning("gemini_json_parse_failed", error=str(e))
             console.print(f"[dim]Warning: Failed to parse Gemini response as JSON: {e}[/dim]")
             return {"genres": [], "moods": [], "instruments": [], "bpm": None, "error": "JSON parse error"}
             
    except Exception as e:
        logger.error("enrich_track_failed", title=title, artist=artist, error=str(e))
        console.print(f"[bold red]Error enriching:[/bold red] {e}")
        return {"genres": ["Error"], "moods": ["Error"], "instruments": [], "bpm": None, "error": str(e)}


def _build_track_data(
    video_id: str,
    title: str,
    track: dict,
    owner: str,
    metadata: dict,
    *,
    is_music: bool = True,
    album_year: str | None = None,
    play_count: str | None = None,
    playable_video_id: str | None = None,
) -> dict:
    """Assemble a track_data dict from raw track info and enrichment metadata.

    Pure function — no I/O, no side effects.
    """
    is_error = bool(metadata.get("error"))

    # Structured artists: [{"name": "...", "id": "..."}]
    raw_artists = track.get("artists", [])
    artists = [
        {
            "name": a.get("name", "Unknown").removesuffix(" - Topic").strip(),
            "id": a.get("id"),
        }
        for a in raw_artists
    ]

    # Structured album: {"name": "...", "id": "..."}
    raw_album = track.get("album")
    album = (
        {"name": raw_album["name"], "id": raw_album.get("id")}
        if raw_album and raw_album.get("name")
        else None
    )

    if not is_music:
        status = "non-music"
    elif is_error:
        status = "error"
    else:
        status = "success"

    # Use playable videoId for the URL so the link actually works
    url_vid = playable_video_id or video_id

    result = {
        "videoId": video_id,
        "title": title,
        "artists": artists,
        "album": album,
        "year": album_year,
        "playCount": play_count,
        "thumbnails": track.get("thumbnails", []),
        "genres": metadata.get("genres", []),
        "moods": metadata.get("moods", []),
        "instruments": metadata.get("instruments", []),
        "bpm": metadata.get("bpm"),
        "isMusic": is_music,
        "status": status,
        "success": is_music and not is_error,
        "error_message": metadata.get("error"),
        "url": f"https://music.youtube.com/watch?v={url_vid}",
        "owner": owner,
    }

    if playable_video_id:
        result["playableVideoId"] = playable_video_id

    return result


def process_playlist(
    playlist_id: str,
    owner: str = "local",
    wipe: bool = False,
    api_key: str | None = None,
    on_progress: callable = None,
    cancel_check: callable = None,
    # --- DI ports (None = construct production adapters) ---
    storage_port: StoragePort | None = None,
    playlist_fetcher: PlaylistFetcher | None = None,
    audio_downloader: AudioDownloader | None = None,
    audio_enricher: AudioEnricher | None = None,
    song_fetcher: SongFetcher | None = None,
    album_fetcher: AlbumFetcher | None = None,
) -> list[dict]:
    """Process a playlist: fetch tracks, deduplicate, download, enrich, and save.

    This is the shared enrichment logic used by both the CLI and the Web API.

    Args:
        playlist_id: YouTube playlist ID to process.
        owner: Owner identifier for user_songs linking.
        wipe: If True, wipe the database before starting.
        api_key: Google/Gemini API key. If None, reads from env or prompts (CLI only).
            Ignored when audio_enricher is provided.
        on_progress: Optional callback receiving a dict with keys:
            current (int), total (int), message (str),
            tokens (int), cost (float), track_data (dict | None).
        cancel_check: Optional callable invoked before each track.
            Should raise an exception (e.g. CancelledError) to abort.
        storage_port: StoragePort implementation. None = TinyDB production adapter.
        playlist_fetcher: PlaylistFetcher implementation. None = YTMusic production adapter.
        audio_downloader: AudioDownloader implementation. None = yt-dlp production adapter.
        audio_enricher: AudioEnricher implementation. None = Gemini production adapter.
        song_fetcher: SongFetcher implementation. None = YTMusic production adapter.
        album_fetcher: AlbumFetcher implementation. None = YTMusic production adapter.

    Returns:
        List of processed track_data dicts.
    """
    from datetime import datetime

    # --- Construct default production adapters when None ---
    if storage_port is None:
        from song_shake.features.enrichment.storage_adapter import TinyDBStorageAdapter
        storage_port = TinyDBStorageAdapter()

    if playlist_fetcher is None:
        from song_shake.features.enrichment.playlist_adapter import YTMusicPlaylistAdapter
        playlist_fetcher = YTMusicPlaylistAdapter()

    if audio_downloader is None:
        from song_shake.features.enrichment.downloader_adapter import YtDlpDownloaderAdapter
        audio_downloader = YtDlpDownloaderAdapter()

    if song_fetcher is None:
        from song_shake.features.enrichment.song_adapter import YTMusicSongAdapter
        song_fetcher = YTMusicSongAdapter()

    if album_fetcher is None:
        from song_shake.features.enrichment.album_adapter import YTMusicAlbumAdapter
        album_fetcher = YTMusicAlbumAdapter()

    if audio_enricher is None:
        # Resolve API key for production Gemini adapter
        load_dotenv()
        if not api_key:
            api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            from rich.prompt import Prompt
            api_key = Prompt.ask("Enter Google API Key", password=True)
            if not api_key:
                console.print("[red]API Key required.[/red]")
                return []
        try:
            from song_shake.features.enrichment.enricher_adapter import GeminiEnricherAdapter
            audio_enricher = GeminiEnricherAdapter(api_key=api_key)
        except Exception as e:
            console.print(f"[red]Error initializing Gemini client: {e}[/red]")
            return []

    # Cache album metadata to avoid repeated get_album calls for same album
    album_cache: dict[str, dict] = {}

    def _fetch_album_year(album_browse_id: str | None) -> str | None:
        """Fetch album year from cache or via album_fetcher."""
        if not album_browse_id:
            return None
        if album_browse_id in album_cache:
            return album_cache[album_browse_id].get("year")
        album_meta = album_fetcher.get_album(album_browse_id)
        album_cache[album_browse_id] = album_meta
        return album_meta.get("year")

    def _report(current: int, total: int, message: str,
                tracker: TokenTracker, track_data: dict | None = None):
        if on_progress is not None:
            on_progress({
                "current": current,
                "total": total,
                "message": message,
                "tokens": tracker.input_tokens + tracker.output_tokens,
                "cost": tracker.get_cost(),
                "track_data": track_data,
            })

    # Create a unique temp directory for this job to avoid collisions
    job_temp_dir = os.path.join(TEMP_DIR_BASE, uuid.uuid4().hex[:12])
    os.makedirs(job_temp_dir, exist_ok=True)

    try:
        if wipe:
            console.print("[yellow]Database wiped.[/yellow]")

        # Fetch tracks
        console.print(f"Fetching tracks for playlist {playlist_id}...")
        tracks = playlist_fetcher.get_tracks(playlist_id)
        if not tracks:
            console.print("No tracks found or error fetching.")
            return []

        results: list[dict] = []
        tracker = TokenTracker()
        total = len(tracks)

        _report(0, total, "Fetching tracks...", tracker)

        with Progress() as progress:
            task = progress.add_task("Processing tracks...", total=total)

            for i, track in enumerate(tracks):
                # Check for cancellation before each track
                if cancel_check is not None:
                    cancel_check()

                video_id = track.get('videoId')
                title = track.get('title', 'Unknown')
                artists_display = ", ".join(
                    a['name'] for a in track.get('artists', [])
                )

                if not video_id:
                    progress.advance(task)
                    continue

                _report(i, total, f"Processing: {title} - {artists_display}", tracker)

                # --- Deduplication: skip if already in global catalog ---
                # When wipe=True (Fresh Scan), re-process every track
                if not wipe:
                    existing_track = storage_port.get_track_by_id(video_id)
                    if existing_track:
                        progress.console.print(
                            f"[dim]Skipping (cached): {title} - {artists_display}[/dim]"
                        )
                        existing_track['owner'] = owner
                        storage_port.save_track(existing_track)
                        progress.advance(task)
                        continue

                # --- Enrich track with per-song ytmusicapi metadata ---
                song_info = song_fetcher.get_song(video_id)
                is_music = song_info.get("isMusic", True)

                # Replace track artists/album/thumbnails with richer ytmusicapi data
                rich_artists = song_info.get("artists", [])
                if rich_artists:
                    track["artists"] = rich_artists
                    artists_display = ", ".join(
                        a["name"] for a in rich_artists
                    )
                rich_album = song_info.get("album")
                if rich_album:
                    track["album"] = rich_album
                rich_thumbs = song_info.get("thumbnails")
                if rich_thumbs:
                    track["thumbnails"] = rich_thumbs
                play_count = song_info.get("playCount")

                # --- Year: prefer song_info, fall back to album_fetcher ---
                album_year = song_info.get("year")
                if not album_year:
                    album_browse_id = (
                        track.get("album", {}).get("id")
                        if track.get("album")
                        else None
                    )
                    album_year = _fetch_album_year(album_browse_id)

                if not is_music:
                    progress.console.print(
                        f"[yellow]Non-music: {title} - {artists_display}[/yellow]"
                    )
                    nonmusic_metadata: dict = {
                        "genres": [], "moods": [], "instruments": [],
                        "bpm": None,
                    }
                    track_data = _build_track_data(
                        video_id, title, track, owner, nonmusic_metadata,
                        is_music=False, album_year=album_year,
                        play_count=play_count,
                    )
                    storage_port.save_track(track_data)
                    results.append(track_data)
                    _report(i, total, f"Non-music: {title}", tracker, track_data)
                    progress.advance(task)
                    continue

                progress.console.print(f"Processing: {title} - {artists_display}")

                # --- Download & enrich ---
                try:
                    filename = audio_downloader.download(video_id, job_temp_dir)
                    metadata = audio_enricher.enrich(
                        filename, title, artists_display,
                    )

                    # Update tracker from enricher usage metadata
                    usage_meta = metadata.pop("usage_metadata", None)
                    tracker.add_usage_from_dict(usage_meta)

                    is_error = bool(metadata.get('error'))
                    if is_error:
                        tracker.failed += 1
                    else:
                        tracker.successful += 1

                    # Cleanup downloaded file
                    if os.path.exists(filename):
                        os.remove(filename)

                    track_data = _build_track_data(
                        video_id, title, track, owner, metadata,
                        is_music=True, album_year=album_year,
                        play_count=play_count,
                    )

                    storage_port.save_track(track_data)
                    results.append(track_data)
                    _report(i, total, f"Processed: {title}", tracker, track_data)

                except Exception as e:
                    console.print(f"[red]Failed to process {title}: {e}[/red]")
                    tracker.failed += 1
                    err_metadata = {
                        "genres": [],
                        "moods": [],
                        "instruments": [],
                        "bpm": None,
                        "error": str(e),
                    }
                    err_track_data = _build_track_data(
                        video_id, title, track, owner, err_metadata,
                        is_music=True, album_year=album_year,
                        play_count=play_count,
                    )
                    storage_port.save_track(err_track_data)
                    results.append(err_track_data)
                    _report(i, total, f"Error: {title}", tracker, err_track_data)

                progress.advance(task)

        _report(total, total, "Enrichment complete", tracker)
        console.print(f"[green]Done! Saved {len(results)} tracks to database.[/green]")
        tracker.print_summary()

        # Save enrichment history
        try:
            storage_port.save_enrichment_history(
                playlist_id,
                owner,
                {
                    'timestamp': datetime.now().isoformat(),
                    'item_count': len(results),
                    'status': 'completed',
                },
            )
        except Exception as h_err:
            console.print(f"[dim]Warning: failed to save history: {h_err}[/dim]")

        return results

    except Exception as e:
        # Save error history
        try:
            storage_port.save_enrichment_history(
                playlist_id,
                owner,
                {
                    'timestamp': datetime.now().isoformat(),
                    'item_count': 0,
                    'status': 'error',
                    'error': str(e),
                },
            )
        except Exception:
            pass
        raise

    finally:
        # Clean up only this job's temp directory
        if os.path.exists(job_temp_dir):
            try:
                shutil.rmtree(job_temp_dir, ignore_errors=True)
            except Exception:
                pass


def retry_failed_tracks(
    owner: str = "local",
    api_key: str | None = None,
    on_progress: callable = None,
    cancel_check: callable = None,
    video_ids: list[str] | None = None,
    # --- DI ports (None = construct production adapters) ---
    storage_port: StoragePort | None = None,
    audio_downloader: AudioDownloader | None = None,
    audio_enricher: AudioEnricher | None = None,
    song_fetcher: SongFetcher | None = None,
    album_fetcher: AlbumFetcher | None = None,
) -> list[dict]:
    """Retry enrichment for failed tracks.

    Re-runs the full pipeline (metadata fetch, download, AI enrich) for
    each error-status track.  When a video is UNPLAYABLE, searches YTMusic
    for a playable alternative and downloads that instead.

    Args:
        owner: Owner identifier for track ownership.
        api_key: Google/Gemini API key.
        on_progress: Callback with dict {current, total, message, tokens, cost, track_data}.
        cancel_check: Callable that raises on cancellation.
        video_ids: Optional list of specific videoIds to retry.
            If None, retries ALL failed tracks for the owner.
        storage_port: StoragePort implementation.
        audio_downloader: AudioDownloader implementation.
        audio_enricher: AudioEnricher implementation.
        song_fetcher: SongFetcher implementation.
        album_fetcher: AlbumFetcher implementation.

    Returns:
        List of updated track_data dicts.
    """
    # --- Construct default production adapters when None ---
    if storage_port is None:
        from song_shake.features.enrichment.storage_adapter import TinyDBStorageAdapter
        storage_port = TinyDBStorageAdapter()

    if audio_downloader is None:
        from song_shake.features.enrichment.downloader_adapter import YtDlpDownloaderAdapter
        audio_downloader = YtDlpDownloaderAdapter()

    if song_fetcher is None:
        from song_shake.features.enrichment.song_adapter import YTMusicSongAdapter
        song_fetcher = YTMusicSongAdapter()

    if album_fetcher is None:
        from song_shake.features.enrichment.album_adapter import YTMusicAlbumAdapter
        album_fetcher = YTMusicAlbumAdapter()

    if audio_enricher is None:
        load_dotenv()
        if not api_key:
            api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            console.print("[red]API Key required for retry.[/red]")
            return []
        try:
            from song_shake.features.enrichment.enricher_adapter import GeminiEnricherAdapter
            audio_enricher = GeminiEnricherAdapter(api_key=api_key)
        except Exception as e:
            console.print(f"[red]Error initializing Gemini client: {e}[/red]")
            return []

    # --- Fetch failed tracks ---
    all_failed = storage_port.get_failed_tracks(owner)
    if video_ids:
        target_set = set(video_ids)
        failed_tracks = [t for t in all_failed if t.get("videoId") in target_set]
    else:
        failed_tracks = all_failed

    if not failed_tracks:
        console.print("[yellow]No failed tracks to retry.[/yellow]")
        return []

    # Cache album metadata
    album_cache: dict[str, dict] = {}

    def _fetch_album_year(album_browse_id: str | None) -> str | None:
        if not album_browse_id:
            return None
        if album_browse_id in album_cache:
            return album_cache[album_browse_id].get("year")
        album_meta = album_fetcher.get_album(album_browse_id)
        album_cache[album_browse_id] = album_meta
        return album_meta.get("year")

    def _report(current: int, total: int, message: str,
                tracker: TokenTracker, track_data: dict | None = None):
        if on_progress is not None:
            on_progress({
                "current": current,
                "total": total,
                "message": message,
                "tokens": tracker.input_tokens + tracker.output_tokens,
                "cost": tracker.get_cost(),
                "track_data": track_data,
            })

    # Create a unique temp directory for this job
    job_temp_dir = os.path.join(TEMP_DIR_BASE, uuid.uuid4().hex[:12])
    os.makedirs(job_temp_dir, exist_ok=True)

    try:
        results: list[dict] = []
        tracker = TokenTracker()
        total = len(failed_tracks)

        _report(0, total, f"Retrying {total} failed track(s)…", tracker)
        console.print(f"Retrying {total} failed track(s)…")

        with Progress() as progress:
            task = progress.add_task("Retrying failed tracks…", total=total)

            for i, failed in enumerate(failed_tracks):
                if cancel_check is not None:
                    cancel_check()

                video_id = failed.get("videoId")
                title = failed.get("title", "Unknown")

                _report(i, total, f"Retrying: {title}", tracker)

                # --- Re-fetch metadata from ytmusicapi ---
                song_info = song_fetcher.get_song(video_id)
                is_music = song_info.get("isMusic", True)
                playable = song_info.get("playable", True)

                # Detect replaced/gone videos: if ytmusicapi returns a
                # completely different title, the original video ID was
                # reassigned to another song on YouTube.
                fetched_title = song_info.get("title") or ""
                stored_title = title
                title_matches = (
                    fetched_title.strip().lower() == stored_title.strip().lower()
                )
                video_replaced = not title_matches and bool(fetched_title)

                if video_replaced:
                    # Don't trust metadata from get_song — it's for a
                    # different song. Force a search using stored title+artist.
                    playable = False  # trigger the search path below

                # Build a track dict — use stored data if video was replaced
                if video_replaced:
                    rich_artists = failed.get("artists", [])
                else:
                    rich_artists = song_info.get("artists") or failed.get("artists", [])
                artists_display = ", ".join(
                    a["name"] for a in rich_artists
                )

                track = {
                    "videoId": video_id,
                    "title": title,
                    "artists": rich_artists,
                    "album": (
                        failed.get("album") if video_replaced
                        else song_info.get("album") or failed.get("album")
                    ),
                    "thumbnails": (
                        failed.get("thumbnails", []) if video_replaced
                        else song_info.get("thumbnails") or failed.get("thumbnails", [])
                    ),
                }

                play_count = (
                    failed.get("playCount") if video_replaced
                    else song_info.get("playCount") or failed.get("playCount")
                )

                # --- Year ---
                album_year = None if video_replaced else song_info.get("year")
                if not album_year:
                    album_browse_id = (
                        track.get("album", {}).get("id")
                        if track.get("album")
                        else None
                    )
                    album_year = _fetch_album_year(album_browse_id)

                if video_replaced:
                    progress.console.print(
                        f"[yellow]REPLACED: '{title}' — original video is now "
                        f"'{fetched_title}'. Searching for correct song…[/yellow]"
                    )
                else:
                    progress.console.print(
                        f"Retrying: {title} - {artists_display}"
                    )

                # --- Determine which videoId to download ---
                download_video_id = video_id
                playable_video_id = None  # stored for frontend playback
                if not playable:
                    if not video_replaced:
                        progress.console.print(
                            f"[yellow]UNPLAYABLE: {title} — searching for alternative…[/yellow]"
                        )
                    alt_vid = song_fetcher.search_playable_alternative(
                        title, artists_display
                    )
                    if alt_vid:
                        download_video_id = alt_vid
                        playable_video_id = alt_vid
                        progress.console.print(
                            f"[green]Found alternative: {alt_vid}[/green]"
                        )
                        # Re-fetch metadata from the playable alternative
                        # to get correct album, artists, thumbnails
                        alt_info = song_fetcher.get_song(alt_vid)
                        alt_artists = alt_info.get("artists") or rich_artists
                        alt_album = alt_info.get("album") or track.get("album")
                        alt_year = alt_info.get("year") or album_year
                        alt_thumbnails = alt_info.get("thumbnails") or track.get("thumbnails", [])
                        alt_play_count = alt_info.get("playCount") or play_count

                        # Update the track with correct metadata
                        track["artists"] = alt_artists
                        track["album"] = alt_album
                        track["thumbnails"] = alt_thumbnails
                        rich_artists = alt_artists
                        artists_display = ", ".join(
                            a["name"] for a in rich_artists
                        )
                        play_count = alt_play_count
                        if alt_year:
                            album_year = alt_year
                    else:
                        reason = (
                            "Video replaced and no alternative found"
                            if video_replaced
                            else "UNPLAYABLE and no alternative found"
                        )
                        progress.console.print(
                            f"[red]No playable alternative found for {title}[/red]"
                        )
                        tracker.failed += 1
                        err_metadata = {
                            "genres": [], "moods": [], "instruments": [],
                            "bpm": None,
                            "error": reason,
                        }
                        err_track_data = _build_track_data(
                            video_id, title, track, owner, err_metadata,
                            is_music=is_music, album_year=album_year,
                            play_count=play_count,
                        )
                        storage_port.save_track(err_track_data)
                        results.append(err_track_data)
                        _report(i, total, f"Failed: {title}", tracker, err_track_data)
                        progress.advance(task)
                        continue

                # --- Download & enrich ---
                try:
                    filename = audio_downloader.download(
                        download_video_id, job_temp_dir
                    )
                    metadata = audio_enricher.enrich(
                        filename, title, artists_display,
                    )

                    usage_meta = metadata.pop("usage_metadata", None)
                    tracker.add_usage_from_dict(usage_meta)

                    is_error = bool(metadata.get("error"))
                    if is_error:
                        tracker.failed += 1
                    else:
                        tracker.successful += 1

                    if os.path.exists(filename):
                        os.remove(filename)

                    track_data = _build_track_data(
                        video_id, title, track, owner, metadata,
                        is_music=is_music, album_year=album_year,
                        play_count=play_count,
                        playable_video_id=playable_video_id,
                    )

                    storage_port.save_track(track_data)
                    results.append(track_data)
                    _report(i, total, f"Retried: {title}", tracker, track_data)

                except Exception as e:
                    console.print(f"[red]Retry failed for {title}: {e}[/red]")
                    tracker.failed += 1
                    err_metadata = {
                        "genres": [], "moods": [], "instruments": [],
                        "bpm": None, "error": str(e),
                    }
                    err_track_data = _build_track_data(
                        video_id, title, track, owner, err_metadata,
                        is_music=is_music, album_year=album_year,
                        play_count=play_count,
                    )
                    storage_port.save_track(err_track_data)
                    results.append(err_track_data)
                    _report(i, total, f"Error: {title}", tracker, err_track_data)

                progress.advance(task)

        _report(total, total, "Retry complete", tracker)
        console.print(f"[green]Retry done! Processed {len(results)} tracks.[/green]")
        tracker.print_summary()
        return results

    finally:
        if os.path.exists(job_temp_dir):
            try:
                shutil.rmtree(job_temp_dir, ignore_errors=True)
            except Exception:
                pass
