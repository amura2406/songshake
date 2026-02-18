import os
import json
from rich.console import Console
from rich.progress import Progress
from rich.table import Table
import yt_dlp
from google import genai
from google.genai import types
from song_shake.features.enrichment import playlist
import shutil
from dotenv import load_dotenv
import time
from song_shake.platform.logging_config import get_logger

logger = get_logger(__name__)

console = Console()

TEMP_DIR = "temp_downloads"

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


def download_track(video_id: str, output_dir: str = TEMP_DIR) -> str:
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

def process_playlist(
    playlist_id: str,
    owner: str = "local",
    wipe: bool = False,
    api_key: str | None = None,
    on_progress: callable = None,
) -> list[dict]:
    """Process a playlist: fetch tracks, deduplicate, download, enrich, and save.

    This is the shared enrichment logic used by both the CLI and the Web API.

    Args:
        playlist_id: YouTube playlist ID to process.
        owner: Owner identifier for user_songs linking.
        wipe: If True, wipe the database before starting.
        api_key: Google/Gemini API key. If None, reads from env or prompts (CLI only).
        on_progress: Optional callback receiving a dict with keys:
            current (int), total (int), message (str),
            tokens (int), cost (float), track_data (dict | None).

    Returns:
        List of processed track_data dicts.
    """
    from song_shake.features.songs import storage
    from datetime import datetime

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

    # Initial cleanup
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR, ignore_errors=True)

    try:
        if wipe:
            storage.wipe_db()
            console.print("[yellow]Database wiped.[/yellow]")

        load_dotenv()

        # Resolve API key
        if not api_key:
            api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            from rich.prompt import Prompt
            api_key = Prompt.ask("Enter Google API Key", password=True)
            if not api_key:
                console.print("[red]API Key required.[/red]")
                return []

        try:
            client = genai.Client(api_key=api_key)
        except Exception as e:
            console.print(f"[red]Error initializing Gemini client: {e}[/red]")
            return []

        # Fetch tracks
        console.print(f"Fetching tracks for playlist {playlist_id}...")
        tracks = playlist.get_tracks(playlist_id)
        if not tracks:
            console.print("No tracks found or error fetching.")
            return []

        results: list[dict] = []
        tracker = TokenTracker()
        db = storage.init_db()
        total = len(tracks)

        _report(0, total, "Fetching tracks...", tracker)

        with Progress() as progress:
            task = progress.add_task("Processing tracks...", total=total)

            for i, track in enumerate(tracks):
                video_id = track.get('videoId')
                title = track.get('title', 'Unknown')
                artists = ", ".join([a['name'] for a in track.get('artists', [])])

                if not video_id:
                    progress.advance(task)
                    continue

                _report(i, total, f"Processing: {title} - {artists}", tracker)

                # --- Deduplication: skip if already in global catalog ---
                existing_track = storage.get_track_by_id(db, video_id)
                if existing_track:
                    progress.console.print(
                        f"[dim]Skipping (cached): {title} - {artists}[/dim]"
                    )
                    existing_track['owner'] = owner
                    storage.save_track(db, existing_track)
                    progress.advance(task)
                    continue

                progress.console.print(f"Processing: {title} - {artists}")

                # Download & enrich
                try:
                    filename = download_track(video_id)
                    metadata = enrich_track(client, filename, title, artists, tracker)

                    is_error = bool(metadata.get('error'))
                    if is_error:
                        tracker.failed += 1
                    else:
                        tracker.successful += 1

                    # Cleanup downloaded file
                    if os.path.exists(filename):
                        os.remove(filename)

                    track_data = {
                        "videoId": video_id,
                        "title": title,
                        "artists": artists,
                        "album": track.get('album', {}).get('name') if track.get('album') else None,
                        "thumbnails": track.get('thumbnails', []),
                        "genres": metadata.get('genres', []),
                        "moods": metadata.get('moods', []),
                        "instruments": metadata.get('instruments', []),
                        "bpm": metadata.get('bpm'),
                        "status": "error" if is_error else "success",
                        "success": not is_error,
                        "error_message": metadata.get('error'),
                        "url": f"https://music.youtube.com/watch?v={video_id}",
                        "owner": owner,
                    }

                    storage.save_track(db, track_data)
                    results.append(track_data)
                    _report(i, total, f"Processed: {title}", tracker, track_data)

                except Exception as e:
                    console.print(f"[red]Failed to process {title}: {e}[/red]")
                    tracker.failed += 1
                    err_track_data = {
                        "videoId": video_id,
                        "title": title,
                        "artists": artists,
                        "album": track.get('album', {}).get('name') if track.get('album') else None,
                        "thumbnails": track.get('thumbnails', []),
                        "genres": [],
                        "moods": [],
                        "instruments": [],
                        "bpm": None,
                        "status": "error",
                        "success": False,
                        "error_message": str(e),
                        "url": f"https://music.youtube.com/watch?v={video_id}",
                        "owner": owner,
                    }
                    storage.save_track(db, err_track_data)
                    results.append(err_track_data)
                    _report(i, total, f"Error: {title}", tracker, err_track_data)

                progress.advance(task)

        _report(total, total, "Enrichment complete", tracker)
        console.print(f"[green]Done! Saved {len(results)} tracks to database.[/green]")
        tracker.print_summary()

        # Save enrichment history
        try:
            storage.save_enrichment_history(
                playlist_id,
                owner,
                {
                    'timestamp': datetime.now().isoformat(),
                    'item_count': len(results),
                    'status': 'completed',
                },
                db,
            )
        except Exception as h_err:
            console.print(f"[dim]Warning: failed to save history: {h_err}[/dim]")

        return results

    except Exception as e:
        # Save error history
        try:
            storage.save_enrichment_history(
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
        # Final cleanup
        if os.path.exists(TEMP_DIR):
            try:
                shutil.rmtree(TEMP_DIR, ignore_errors=True)
            except Exception:
                pass
