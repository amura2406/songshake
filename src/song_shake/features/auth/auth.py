import json
import time
from rich.prompt import Prompt
from rich import print
from ytmusicapi import YTMusic
import os
from ytmusicapi.auth.oauth import OAuthCredentials

import requests
from song_shake.platform.logging_config import get_logger

logger = get_logger(__name__)

OAUTH_FILE = "oauth.json"
def get_ytmusic() -> YTMusic:
    if not os.path.exists(OAUTH_FILE):
        # Fallback to checking if we can init from env but usually we need the file
        print(f"[bold red]Auth file {OAUTH_FILE} not found. Please run 'song-shake auth' first.[/bold red]")
        raise FileNotFoundError("Auth file not found")
        
    # Robust init logic from api.py
    with open(OAUTH_FILE) as f:
        auth_data = json.load(f)
    
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

def ensure_fresh_access_token() -> str:
    """Read oauth.json, refresh if expired, return a valid access_token.

    Raises ValueError if no valid token can be obtained.
    """
    if not os.path.exists(OAUTH_FILE):
        raise ValueError("OAUTH_FILE not found")

    with open(OAUTH_FILE) as f:
        auth_data = json.load(f)

    token = auth_data.get("access_token")
    expires_at = auth_data.get("expires_at")

    # If token is still valid, return it directly
    if token and expires_at and time.time() < expires_at:
        return token

    # Attempt refresh
    refresh_tok = auth_data.get("refresh_token")
    if not refresh_tok:
        raise ValueError("Access token expired and no refresh_token available")

    client_id = auth_data.get("client_id") or os.getenv("GOOGLE_CLIENT_ID")
    client_secret = auth_data.get("client_secret") or os.getenv("GOOGLE_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise ValueError("Missing client credentials for token refresh")

    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_tok,
            "grant_type": "refresh_token",
        },
        timeout=10,
    )
    resp.raise_for_status()
    new_tokens = resp.json()

    auth_data["access_token"] = new_tokens["access_token"]
    auth_data["expires_in"] = new_tokens.get("expires_in", 3600)
    auth_data["expires_at"] = int(time.time()) + auth_data["expires_in"]
    if "refresh_token" in new_tokens:
        auth_data["refresh_token"] = new_tokens["refresh_token"]

    with open(OAUTH_FILE, "w") as f:
        json.dump(auth_data, f)

    logger.info("access_token_refreshed", expires_at=auth_data["expires_at"])
    return auth_data["access_token"]


def get_data_api_playlists(yt: YTMusic, limit: int = 50, access_token: str | None = None):
    """Fallback to YouTube Data API if ytmusicapi fails.

    Args:
        yt: YTMusic instance (unused but kept for API compatibility).
        limit: Maximum number of playlists to return.
        access_token: Google OAuth access token. If None, falls back to
            ensure_fresh_access_token() for CLI compatibility.
    """
    token = access_token or ensure_fresh_access_token()

    headers = {'Authorization': f"Bearer {token}"}
    api_url = "https://www.googleapis.com/youtube/v3/playlists"
    params = {
        'part': 'snippet,contentDetails',
        'mine': 'true',
        'maxResults': min(limit, 50)
    }
    
    res = requests.get(api_url, headers=headers, params=params, timeout=10)
    res.raise_for_status()
    data = res.json()
    
    playlists = []
    for item in data.get('items', []):
        snippet = item['snippet']
        thumbs = snippet.get('thumbnails', {})
        # ytmusicapi usually returns a list sorted by quality.
        # Data API keys: default, medium, high, standard, maxres
        thumb_list = []
        for key in ['default', 'medium', 'high', 'standard', 'maxres']:
            if key in thumbs:
                t = thumbs[key]
                thumb_list.append({
                    'url': t.get('url'),
                    'width': t.get('width'),
                    'height': t.get('height')
                })
        
        playlists.append({
            'playlistId': item['id'],
            'title': snippet['title'],
            'thumbnails': thumb_list,
            'count': item['contentDetails']['itemCount'],
            'description': snippet['description']
        })
    return playlists

def get_data_api_tracks(yt: YTMusic, playlist_id: str, limit: int = 500, access_token: str | None = None):
    """Fallback to YouTube Data API to get tracks.

    Args:
        yt: YTMusic instance (unused but kept for API compatibility).
        playlist_id: YouTube playlist ID.
        limit: Maximum number of tracks to return.
        access_token: Google OAuth access token. If None, falls back to
            ensure_fresh_access_token() for CLI compatibility.
    """
    token = access_token or ensure_fresh_access_token()

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
        
        res = requests.get(api_url, headers=headers, params=params, timeout=10)
        res.raise_for_status()
        data = res.json()
        
        for item in data.get('items', []):
            snippet = item['snippet']
            resource = snippet.get('resourceId', {})
            if resource.get('kind') == 'youtube#video':
                # Strip "- Topic" suffix from auto-generated music channels
                raw_artist = snippet.get('videoOwnerChannelTitle', 'Unknown')
                artist_name = raw_artist.removesuffix(' - Topic').strip()
                # Map to YTMusic track format as best as possible
                tracks.append({
                    'videoId': resource['videoId'],
                    'title': snippet['title'],
                    'artists': [{'name': artist_name}],
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
        YTMusic.setup(filepath=OAUTH_FILE, headers_raw=data)
        print(f"[bold green]Successfully saved {OAUTH_FILE}[/bold green]")

        # Verify the saved auth file works
        YTMusic(OAUTH_FILE)
        print("Auth successful! Headers look valid.")
        
    except Exception as e:
        print(f"[bold red]Error parsing headers or authenticating:[/bold red] {e}")
