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
        db.upsert(track_data, (Song.videoId == video_id) & (Song.owner == owner))
    else:
        db.insert(track_data)

def save_enrichment_history(playlist_id: str, owner: str, metadata: dict, db: TinyDB = None):
    """Save enrichment history for a playlist."""
    if db is None:
        db = init_db()
    
    history_table = db.table('history')
    History = Query()
    
    record = {
        'playlistId': playlist_id,
        'owner': owner,
        'last_processed': metadata.get('timestamp'),
        'item_count': metadata.get('item_count', 0),
        'status': metadata.get('status', 'completed')
    }
    # Include error if present
    if 'error' in metadata:
        record['error'] = metadata['error']
    
    history_table.upsert(record, (History.playlistId == playlist_id) & (History.owner == owner))

def get_enrichment_history(owner: str, db: TinyDB = None) -> dict:
    """Get enrichment history for all playlists of an owner. Returns dict keyed by playlistId."""
    if db is None:
        db = init_db()
    
    history_table = db.table('history')
    History = Query()
    records = history_table.search(History.owner == owner)
    
    return {r['playlistId']: r for r in records}

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

def get_tags(db: TinyDB = None, owner: str = 'local') -> dict:
    """Get all unique moods and genres from the database, sorted by count."""
    if db is None:
        db = init_db()
    Song = Query()
    tracks = db.search(Song.owner == owner)

    tags = {}
    success_count = 0
    failed_count = 0
    
    for track in tracks:
        # Count statuses
        is_success = track.get('success', track.get('status') == 'success')
        if is_success:
            success_count += 1
        else:
            failed_count += 1

        for genre in track.get('genres', []):
            tags[genre] = tags.get(genre, {'type': 'genre', 'count': 0})
            tags[genre]['count'] += 1
        for mood in track.get('moods', []):
            tags[mood] = tags.get(mood, {'type': 'mood', 'count': 0})
            tags[mood]['count'] += 1

    # Convert to sorted list
    result = []
    for name, data in tags.items():
        result.append({'name': name, 'type': data['type'], 'count': data['count']})
    
    result.sort(key=lambda x: x['count'], reverse=True)
    
    # Prepend statuses
    result.insert(0, {'name': 'Failed', 'type': 'status', 'count': failed_count})
    result.insert(0, {'name': 'Success', 'type': 'status', 'count': success_count})
    
    return result

def get_all_history(db: TinyDB = None) -> dict:
    """Get enrichment history for all owners. Returns dict keyed by playlistId (latest wins if duplicates)."""
    if db is None:
        db = init_db()
    history_table = db.table('history')
    return {r['playlistId']: r for r in history_table.all()}
