from tinydb import TinyDB, Query
from pathlib import Path

STORAGE_FILE = "songs.db"

def init_db(path: str = STORAGE_FILE) -> TinyDB:
    return TinyDB(path)

def save_track(db: TinyDB, track_data: dict):
    """Save or update track in global catalog and link to user."""
    songs_table = db.table('songs')
    user_songs_table = db.table('user_songs')
    Song = Query()
    UserSong = Query()
    
    video_id = track_data.get('videoId')
    owner = track_data.get('owner', 'local')
    
    # Remove owner from global track_data if present to keep catalog generic
    track_data.pop('owner', None)
    
    if video_id:
        songs_table.upsert(track_data, Song.videoId == video_id)
        # Link user to this videoId if not already linked
        if not user_songs_table.search((UserSong.owner == owner) & (UserSong.videoId == video_id)):
            user_songs_table.insert({'owner': owner, 'videoId': video_id})
    else:
        # Fallback if no videoId (should rarely happen)
        songs_table.insert(track_data)

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
    
    songs_table = db.table('songs')
    user_songs_table = db.table('user_songs')
    UserSong = Query()
    
    # Get all videoIds linked to this owner
    user_links = user_songs_table.search(UserSong.owner == owner)
    video_ids = [link.get('videoId') for link in user_links if link.get('videoId')]
    
    if not video_ids:
        return []
    
    # Build a small list of matching global songs
    # TinyDB doesn't have an 'in' operator natively but we can use any() or check manually
    # The safest way is to just fetch the whole songs table (or matching) if small, 
    # but test_filter works by doing a manual loop
    
    all_songs = songs_table.all()
    user_songs = [s for s in all_songs if s.get('videoId') in video_ids]
    
    return user_songs

def get_track_by_id(db: TinyDB, video_id: str) -> dict:
    """Check if track exists in the global catalog by videoId."""
    if db is None:
        db = init_db()
    songs_table = db.table('songs')
    Song = Query()
    result = songs_table.search(Song.videoId == video_id)
    return result[0] if result else None

def get_tags(db: TinyDB = None, owner: str = 'local') -> dict:
    """Get all unique moods and genres from the database, sorted by count."""
    if db is None:
        db = init_db()
    
    tracks = get_all_tracks(db, owner)

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
