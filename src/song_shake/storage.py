from tinydb import TinyDB, Query
from pathlib import Path

STORAGE_FILE = "songs.db"

def init_db(path: str = STORAGE_FILE) -> TinyDB:
    return TinyDB(path)

def save_track(db: TinyDB, track_data: dict):
    """Save or update track in database by videoId."""
    Song = Query()
    video_id = track_data.get('videoId')
    if video_id:
        db.upsert(track_data, Song.videoId == video_id)
    else:
        db.insert(track_data)

def wipe_db(path: str = STORAGE_FILE):
    """Wipe the database file."""
    if Path(path).exists():
        # Truncate content or remove file
        # TinyDB truncate() might be safer if we want to keep file handle, 
        # but initializing new DB after remove is fine too.
        # Actually TinyDB.truncate() exists.
        db = TinyDB(path)
        db.truncate()
        db.close()

def get_all_tracks(db: TinyDB = None) -> list:
    """Get all tracks from database."""
    if db is None:
        db = init_db()
    return db.all()
