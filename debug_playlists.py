from ytmusicapi import YTMusic
import json
import os

if not os.path.exists("oauth.json"):
    print("oauth.json not found")
    exit(1)

try:
    yt = YTMusic("oauth.json")
    print("Authenticated.")
    
    print("Fetching library playlists...")
    playlists = yt.get_library_playlists(limit=50)
    print(f"Found {len(playlists)} playlists.")
    if len(playlists) > 0:
        print("First playlist sample:")
        print(json.dumps(playlists[0], indent=2))
    else:
        print("No playlists found in library.")
        
    print("Fetching liked songs...")
    try:
        liked = yt.get_liked_songs(limit=5)
        print(f"Found {liked['trackCount']} liked songs (approx).")
        print(f"Tracks in response: {len(liked['tracks'])}")
    except Exception as e:
        print(f"Error fetching liked songs: {e}")
        
    print("Fetching home...")
    try:
        home = yt.get_home(limit=1)
        print(f"Home sections found: {len(home)}")
    except Exception as e:
        print(f"Error fetching home: {e}")
        
except Exception as e:
    print(f"Error: {e}")
