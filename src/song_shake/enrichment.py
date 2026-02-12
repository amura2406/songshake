import os
import json
from rich.console import Console
from rich.progress import Progress
from rich.table import Table
import yt_dlp
from google import genai
from google.genai import types
from song_shake import playlist
import shutil
from dotenv import load_dotenv
import time

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
        - genres: list of strings (e.g. "Pop", "Rock", "Indie")
        - moods: list of strings (e.g. "Happy", "Sad", "Energetic")
        
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
             import json
             data = json.loads(response.text)
             return data
        except:
             return {"genres": [], "moods": [], "error": "JSON parse error"}
             
    except Exception as e:
        console.print(f"[bold red]Error enriching:[/bold red] {e}")
        return {"genres": ["Error"], "moods": ["Error"], "error": str(e)}

def process_playlist(playlist_id: str, owner: str = "local", wipe: bool = False):
    # Initial cleanup
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR, ignore_errors=True)

    try:
        if wipe:
            from song_shake import storage
            storage.wipe_db()
            console.print("[yellow]Database wiped.[/yellow]")

        load_dotenv()
        
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            from rich.prompt import Prompt
            api_key = Prompt.ask("Enter Google API Key", password=True)
            if not api_key:
                console.print("[red]API Key required.[/red]")
                return

        try:
            client = genai.Client(api_key=api_key)
        except Exception as e:
            console.print(f"[red]Error initializing Gemini client: {e}[/red]")
            return
        
        # Verify playlist
        console.print(f"Fetching tracks for playlist {playlist_id}...")
        tracks = playlist.get_tracks(playlist_id)
        if not tracks:
            console.print("No tracks found or error fetching.")
            return

        results = []
        tracker = TokenTracker()
        
        with Progress() as progress:
            task = progress.add_task("Processing tracks...", total=len(tracks))
            
            for track in tracks:
                video_id = track.get('videoId')
                title = track.get('title')
                artists = ", ".join([a['name'] for a in track.get('artists', [])])
                
                if not video_id:
                    progress.advance(task)
                    continue
                    
                progress.console.print(f"Processing: {title} - {artists}")
                
                # Download
                try:
                    filename = download_track(video_id)
                    
                    # Enrich
                    metadata = enrich_track(client, filename, title, artists, tracker)
                    
                    # Check for error in metadata
                    if metadata.get('error') or "Error" in metadata.get('genres', []):
                        tracker.failed += 1
                    else:
                        tracker.successful += 1
                    
                    # Cleanup specific file (optional now but good to keep to save space during run)
                    if os.path.exists(filename):
                        os.remove(filename)
                    
                    track_data = {
                        "videoId": video_id,
                        "title": title,
                        "artists": artists,
                        "album": track.get('album', {}).get('name') if track.get('album') else None,
                        "genres": metadata.get('genres', []),
                        "moods": metadata.get('moods', []),
                        "status": "error" if metadata.get('error') else "success",
                        "error_message": metadata.get('error'),
                        "url": f"https://music.youtube.com/watch?v={video_id}",
                        "owner": "local" # CLI default, overridden by caller if needed (actually caller can't override easily unless we pass it in, but we can set it before saving)
                    }
                    results.append(track_data)
                    
                except Exception as e:
                     console.print(f"[red]Failed to process {title}: {e}[/red]")
                     tracker.failed += 1
                     results.append({
                        "videoId": video_id,
                        "title": title,
                        "artists": artists,
                        "status": "error",
                        "error_message": str(e)
                     })
                
                progress.advance(task)

        # Save results to TinyDB
        from song_shake import storage
        db = storage.init_db()
        for res in results:
            storage.save_track(db, res)
        console.print(f"[green]Done! Saved {len(results)} tracks to database.[/green]")
        
        # Print Summary
        tracker.print_summary()

    finally:
        # Final cleanup
        if os.path.exists(TEMP_DIR):
            try:
                shutil.rmtree(TEMP_DIR, ignore_errors=True)
            except Exception:
                pass
