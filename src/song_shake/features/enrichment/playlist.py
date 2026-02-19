from rich.console import Console
from rich.table import Table
from song_shake.features.auth.auth import get_ytmusic

console = Console()


def list_playlists():
    try:
        yt = get_ytmusic()
        playlists = yt.get_library_playlists(limit=50)

        table = Table(title="Your Playlists")
        table.add_column("ID", style="cyan")
        table.add_column("Title", style="magenta")
        table.add_column("Count", justify="right")

        for pl in playlists:
            count = pl.get('count', '?')
            if count is None:
                count = '?'
            table.add_row(pl['playlistId'], pl['title'], str(count))

        console.print(table)
    except Exception as e:
        console.print(f"[bold red]Error fetching playlists:[/bold red] {e}")


def get_tracks(playlist_id: str):
    yt = get_ytmusic()
    try:
        playlist = yt.get_playlist(playlist_id, limit=None)
        return playlist.get('tracks', [])
    except Exception as e:
        console.print(
            f"[yellow]YTMusic get_playlist failed for {playlist_id}: {e}[/yellow]"
        )
        # Fallback to YouTube Data API v3 (handles regular YouTube playlists)
        from song_shake.features.auth import auth
        try:
            console.print("[yellow]Falling back to Data API for tracks...[/yellow]")
            return auth.get_data_api_tracks(yt, playlist_id)
        except Exception as e2:
            console.print(
                f"[bold red]Error fetching tracks for {playlist_id}:"
                f"[/bold red] {e} -> {e2}"
            )
        return []


def get_playlist_title(playlist_id: str) -> str:
    yt = get_ytmusic()
    try:
        playlist = yt.get_playlist(playlist_id, limit=1)
        return playlist['title']
    except Exception:
        return "Unknown Playlist"
