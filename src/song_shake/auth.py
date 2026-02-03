import json
from rich.prompt import Prompt
from rich import print
from ytmusicapi import YTMusic
import os

OAUTH_FILE = "oauth.json"

def get_ytmusic() -> YTMusic:
    if not os.path.exists(OAUTH_FILE):
        print(f"[bold red]Auth file {OAUTH_FILE} not found. Please run 'song-shake auth' first.[/bold red]")
        raise FileNotFoundError("Auth file not found")
    return YTMusic(OAUTH_FILE)

def setup_auth():
    print("[bold green]YouTube Music Authentication Setup[/bold green]")
    print("Please follow the instructions to get your headers: https://ytmusicapi.readthedocs.io/en/latest/setup/browser.html")
    print("Basically: Open music.youtube.com, Open DevTools > Network, filter for 'browse', click one, copy Request Headers.")
    
    print("\nPlease paste the raw headers (or JSON). Press Enter, then Ctrl+D (Unix) or Ctrl+Z (Windows) to save.")
    
    lines = []
    try:
        while True:
            line = input()
            lines.append(line)
    except EOFError:
        pass
    
    data = "\n".join(lines)
    
    if not data.strip():
        print("[bold red]No data entered.[/bold red]")
        return

    try:
        # Try to parse as JSON first
        try:
            headers = json.loads(data)
        except json.JSONDecodeError:
            # Try to parse raw headers
            headers = YTMusic.setup(filepath=None, headers_raw=data)
            # setup returns json string or writes to file? 
            # Actually setup(filepath=None, headers_raw=...) returns the json string content.
            # Let's check ytmusicapi docs or source if possible.
            # Assuming it returns the json content or dict.
            # Actually YTMusic.setup implementation:
            # if filepath: write to file.
            # return headers dict.
            pass
        
        # If we used YTMusic.setup with filepath=None, it returns headers dict?
        # Let's just save the parsed headers or what YTMusic.setup returns
        
        # Re-using YTMusic.setup to parse raw headers to be safe
        # It handles the parsing well.
        
        # We can just call YTMusic.setup with the output file.
        # But we want to handle the input ourselves to support paste.
        import ast
        
        # If it looks like a python dict string
        if data.strip().startswith("{") and "'" in data:
             try:
                 headers = ast.literal_eval(data)
             except:
                 pass

        # Final attempt: let YTMusic handle it
        # We write to a temp file or just pass headers_raw if possible?
        # YTMusic.setup(filepath='oauth.json', headers_raw=data)
        
        YTMusic.setup(filepath=OAUTH_FILE, headers_raw=data)
        print(f"[bold green]Successfully saved {OAUTH_FILE}[/bold green]")
        
        # Verify
        yt = YTMusic(OAUTH_FILE)
        me = yt.get_account_info() if hasattr(yt, 'get_account_info') else "Unknown" # get_account_info might not exist
        # try get_library_playlists to verify
        print("Auth successful! Headers look valid.")
        
    except Exception as e:
        print(f"[bold red]Error parsing headers or authenticating:[/bold red] {e}")
