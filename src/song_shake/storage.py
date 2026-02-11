from tinydb import TinyDB, Query
from pathlib import Path

STORAGE_FILE = "songs.db"

def init_db(path: str = STORAGE_FILE) -> TinyDB:
    return TinyDB(path)

def save_track(db: TinyDB, track_data: dict):
    """Save or update track in database by videoId."""
    Song = Query()
    video_id = track_data.get('videoId')
    owner = track_data.get('owner', 'local')  # Default to 'local' for CLI
    
    # Ensure owner is set in track_data
    track_data['owner'] = owner
    
    if video_id:
        # Update if videoId AND owner match (since different owners might have same song? 
        # Actually same song is same song, but maybe we want to separate collections?
        # The requirement says "songs DB now has to include "owner" as to who is logged in at the time, since it will only show result for the particular logged in user."
        # So yes, we should probably scope by owner.
        db.upsert(track_data, (Song.videoId == video_id) & (Song.owner == owner))
    else:
        db.insert(track_data)

def wipe_db(path: str = STORAGE_FILE):
    """Wipe the database file."""
    if Path(path).exists():
        db = TinyDB(path)
        db.truncate()
        db.close()

def get_all_tracks(db: TinyDB = None, owner: str = 'local') -> list:
    """Get all tracks from database for a specific owner."""
    if db is None:
        db = init_db()
    Song = Query()
    return db.search(Song.owner == owner)
