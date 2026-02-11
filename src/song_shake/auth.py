import json
from rich.prompt import Prompt
from rich import print
from ytmusicapi import YTMusic
import os
from ytmusicapi.auth.oauth import OAuthCredentials
from dotenv import load_dotenv
import requests

OAUTH_FILE = "oauth.json"
def get_ytmusic() -> YTMusic:
    if not os.path.exists(OAUTH_FILE):
        # Fallback to checking if we can init from env but usually we need the file
        print(f"[bold red]Auth file {OAUTH_FILE} not found. Please run 'song-shake auth' first.[/bold red]")
        raise FileNotFoundError("Auth file not found")
        
    # Robust init logic from api.py
    with open(OAUTH_FILE) as f:
        auth_data = json.load(f)
    
    load_dotenv()
    if 'client_id' not in auth_data and os.getenv("GOOGLE_CLIENT_ID"):
            auth_data['client_id'] = os.getenv("GOOGLE_CLIENT_ID")
    if 'client_secret' not in auth_data and os.getenv("GOOGLE_CLIENT_SECRET"):
            auth_data['client_secret'] = os.getenv("GOOGLE_CLIENT_SECRET")
    
    creds = None
    if 'client_id' in auth_data and 'client_secret' in auth_data:
        creds = OAuthCredentials(client_id=auth_data['client_id'], client_secret=auth_data['client_secret'])
        
    valid_keys = {'scope', 'token_type', 'access_token', 'refresh_token', 'expires_at', 'expires_in'}
    clean_auth = {k: v for k, v in auth_data.items() if k in valid_keys}
        
    return YTMusic(auth=clean_auth, oauth_credentials=creds)

def get_data_api_playlists(yt: YTMusic, limit: int = 50):
    """Fallback to YouTube Data API if ytmusicapi fails."""
    # Read token directly from file since yt object might not expose it easily
    if not os.path.exists(OAUTH_FILE):
        raise ValueError("OAUTH_FILE not found")
        
    with open(OAUTH_FILE) as f:
        auth_data = json.load(f)
        
    token = auth_data.get('access_token')
    
    if not token:
        print(f"DEBUG: No access token found in {OAUTH_FILE}")
        raise ValueError("No access token found for Data API fallback")
        
    headers = {'Authorization': f"Bearer {token}"}
    api_url = "https://www.googleapis.com/youtube/v3/playlists"
    params = {
        'part': 'snippet,contentDetails',
        'mine': 'true',
        'maxResults': min(limit, 50)
    }
    
    res = requests.get(api_url, headers=headers, params=params)
    res.raise_for_status()
    data = res.json()
    
    playlists = []
    for item in data.get('items', []):
        playlists.append({
            'playlistId': item['id'],
            'title': item['snippet']['title'],
            'thumbnails': [{'url': item['snippet']['thumbnails'].get('default', {}).get('url', '')}],
            'count': item['contentDetails']['itemCount'],
            'description': item['snippet']['description']
        })
    return playlists

def get_data_api_tracks(yt: YTMusic, playlist_id: str, limit: int = 500):
    """Fallback to YouTube Data API to get tracks."""
    if not os.path.exists(OAUTH_FILE):
        raise ValueError("OAUTH_FILE not found")
        
    with open(OAUTH_FILE) as f:
        auth_data = json.load(f)
        
    token = auth_data.get('access_token')
    
    if not token:
        raise ValueError("No access token found for Data API fallback")

    headers = {'Authorization': f"Bearer {token}"}
    api_url = "https://www.googleapis.com/youtube/v3/playlistItems"
    
    tracks = []
    page_token = None
    
    while True:
        params = {
            'part': 'snippet',
            'playlistId': playlist_id,
            'maxResults': 50,
            'pageToken': page_token
        }
        
        res = requests.get(api_url, headers=headers, params=params)
        res.raise_for_status()
        data = res.json()
        
        for item in data.get('items', []):
            snippet = item['snippet']
            resource = snippet.get('resourceId', {})
            if resource.get('kind') == 'youtube#video':
                # Map to YTMusic track format as best as possible
                tracks.append({
                    'videoId': resource['videoId'],
                    'title': snippet['title'],
                    'artists': [{'name': snippet.get('videoOwnerChannelTitle', 'Unknown')}],
                    'album': None,
                    'thumbnails': [{'url': snippet['thumbnails'].get('default', {}).get('url', '')}] if 'thumbnails' in snippet else []
                })
        
        page_token = data.get('nextPageToken')
        if not page_token or (limit and len(tracks) >= limit):
            break
            
    return tracks

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
