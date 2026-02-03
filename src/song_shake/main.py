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
def show():
    """Show enriched songs from the database."""
    from song_shake import storage
    from rich.table import Table
    from rich.console import Console
    
    console = Console()
    tracks = storage.get_all_tracks()
    
    if not tracks:
        console.print("[yellow]No songs in database.[/yellow]")
        return
        
    table = Table(title="Enriched Songs")
    table.add_column("Title", style="cyan")
    table.add_column("Artist", style="magenta")
    table.add_column("Genres", style="green")
    table.add_column("Moods", style="yellow")
    table.add_column("Status", style="blue")
    
    for track in tracks:
        genres = ", ".join(track.get('genres', []))
        moods = ", ".join(track.get('moods', []))
        if len(genres) > 30: genres = genres[:27] + "..."
        if len(moods) > 30: moods = moods[:27] + "..."
        
        table.add_row(
            track.get('title', 'Unknown'),
            track.get('artists', 'Unknown'),
            genres,
            moods,
            track.get('status', 'Unknown')
        )
        
    console.print(table)

if __name__ == "__main__":
    app()
