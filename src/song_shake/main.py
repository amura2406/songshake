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

if __name__ == "__main__":
    app()
