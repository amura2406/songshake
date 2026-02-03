import typer
from rich import print
from song_shake import auth, playlist, enrichment

app = typer.Typer()

@app.command()
def setup_auth():
    """Setup YouTube Music authentication."""
    auth.setup_auth()

@app.command()
def list_playlists():
    """List available playlists."""
    playlist.list_playlists()

@app.command()
def enrich(playlist_id: str, wipe: bool = typer.Option(False, "--wipe", "-w", help="Wipe database before starting")):
    """Enrich a playlist with metadata."""
    enrichment.process_playlist(playlist_id, wipe=wipe)

@app.command()
def show(
    limit: int = typer.Option(100, "--limit", "-l", help="Number of rows to show"),
    genre: str = typer.Option(None, "--genre", "-g", help="Filter by genre (case-insensitive)"),
    mood: str = typer.Option(None, "--mood", "-m", help="Filter by mood (case-insensitive)"),
):
    """Show enriched songs from the database."""
    from song_shake import storage
    from rich.table import Table
    from rich.console import Console
    
    console = Console()
    tracks = storage.get_all_tracks()
    
    if not tracks:
        console.print("[yellow]No songs in database.[/yellow]")
        return
        
    # Filtering
    filtered_tracks = []
    for t in tracks:
        # Genre filter
        if genre:
            t_genres = [g.lower() for g in t.get('genres', [])]
            if not any(genre.lower() in g for g in t_genres):
                continue
        
        # Mood filter
        if mood:
            t_moods = [m.lower() for m in t.get('moods', [])]
            if not any(mood.lower() in m for m in t_moods):
                continue
                
        filtered_tracks.append(t)
    
    # Limiting
    display_tracks = filtered_tracks[:limit]
    
    table = Table(title=f"Enriched Songs ({len(display_tracks)}/{len(filtered_tracks)} shown)")
    table.add_column("No", style="dim")
    table.add_column("Title", style="cyan")
    table.add_column("Artist", style="magenta")
    table.add_column("Genres", style="green")
    table.add_column("Moods", style="yellow")
    table.add_column("Status", style="blue")
    
    for idx, track in enumerate(display_tracks, 1):
        genres = ", ".join(track.get('genres', []))
        moods = ", ".join(track.get('moods', []))
        # No truncation as requested
        
        table.add_row(
            str(idx),
            track.get('title', 'Unknown'),
            track.get('artists', 'Unknown'),
            genres,
            moods,
            track.get('status', 'Unknown')
        )
        
    console.print(table)
    if len(display_tracks) < len(filtered_tracks):
        console.print(f"[dim]... and {len(filtered_tracks) - len(display_tracks)} more. Use --limit to see more.[/dim]")

if __name__ == "__main__":
    app()
