import threading

from tinydb import TinyDB, Query
from pathlib import Path

STORAGE_FILE = "songs.db"

# Module-level lock protects all TinyDB operations against concurrent access
# from multiple background threads (FastAPI BackgroundTasks uses a thread pool).
_db_lock = threading.Lock()

# Singleton TinyDB instance — prevents stale _last_id caches when
# multiple callers (concurrent enrichment jobs) access the same file.
_db_instance: TinyDB | None = None
_db_instance_path: str | None = None


def init_db(path: str = STORAGE_FILE) -> TinyDB:
    """Return a singleton TinyDB instance for the given path."""
    global _db_instance, _db_instance_path
    if _db_instance is None or _db_instance_path != path:
        _db_instance = TinyDB(path)
        _db_instance_path = path
    return _db_instance


def _safe_write(table, operation: str, *args, max_retries: int = 3, **kwargs):
    """Execute a TinyDB write with retry on document-ID collision.

    TinyDB's auto-increment IDs can collide under concurrent writes.
    On collision (ValueError), clear the table cache to refresh _last_id
    from disk, then retry.
    """
    for attempt in range(max_retries):
        try:
            return getattr(table, operation)(*args, **kwargs)
        except ValueError as e:
            if "already exists" in str(e) and attempt < max_retries - 1:
                table.clear_cache()
                continue
            raise


def save_track(db: TinyDB, track_data: dict):
    """Save or update track in global catalog and link to user."""
    with _db_lock:
        songs_table = db.table('songs')
        user_songs_table = db.table('user_songs')
        Song = Query()
        UserSong = Query()

        video_id = track_data.get('videoId')
        owner = track_data.get('owner', 'local')

        # Remove owner from global track_data if present to keep catalog generic
        track_data.pop('owner', None)

        if video_id:
            _safe_write(songs_table, 'upsert', track_data, Song.videoId == video_id)
            # Link user to this videoId if not already linked
            if not user_songs_table.search((UserSong.owner == owner) & (UserSong.videoId == video_id)):
                try:
                    _safe_write(user_songs_table, 'insert', {'owner': owner, 'videoId': video_id})
                except ValueError:
                    pass  # Link already exists or collision resolved
        else:
            # Fallback if no videoId (should rarely happen)
            _safe_write(songs_table, 'insert', track_data)

def save_enrichment_history(playlist_id: str, owner: str, metadata: dict, db: TinyDB = None):
    """Save enrichment history for a playlist."""
    with _db_lock:
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

        _safe_write(history_table, 'upsert', record, (History.playlistId == playlist_id) & (History.owner == owner))

def get_enrichment_history(owner: str, db: TinyDB = None) -> dict:
    """Get enrichment history for all playlists of an owner. Returns dict keyed by playlistId."""
    with _db_lock:
        if db is None:
            db = init_db()

        history_table = db.table('history')
        History = Query()
        records = history_table.search(History.owner == owner)

        return {r['playlistId']: r for r in records}

def wipe_db(path: str = STORAGE_FILE):
    """Wipe the database file."""
    with _db_lock:
        if Path(path).exists():
            db = TinyDB(path)
            db.truncate()
            db.close()

def get_all_tracks(db: TinyDB = None, owner: str = 'local') -> list:
    """Get all tracks from database for a specific owner."""
    with _db_lock:
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

        all_songs = songs_table.all()
        user_songs = [s for s in all_songs if s.get('videoId') in video_ids]

        return user_songs

def get_failed_tracks(db: TinyDB = None, owner: str = 'local') -> list:
    """Get all error-status tracks from database for a specific owner."""
    with _db_lock:
        if db is None:
            db = init_db()

        songs_table = db.table('songs')
        user_songs_table = db.table('user_songs')
        UserSong = Query()
        Song = Query()

        # Get all videoIds linked to this owner
        user_links = user_songs_table.search(UserSong.owner == owner)
        video_ids = [link.get('videoId') for link in user_links if link.get('videoId')]

        if not video_ids:
            return []

        all_error_songs = songs_table.search(Song.status == 'error')
        return [s for s in all_error_songs if s.get('videoId') in video_ids]


def get_track_by_id(db: TinyDB, video_id: str) -> dict:
    """Check if track exists in the global catalog by videoId."""
    with _db_lock:
        if db is None:
            db = init_db()
        songs_table = db.table('songs')
        Song = Query()
        result = songs_table.search(Song.videoId == video_id)
        return result[0] if result else None

def get_tags(db: TinyDB = None, owner: str = 'local') -> dict:
    """Get all unique moods and genres from the database, sorted by count."""
    with _db_lock:
        if db is None:
            db = init_db()

        # Inline track fetching to avoid nested lock acquisition
        songs_table = db.table('songs')
        user_songs_table = db.table('user_songs')
        UserSong = Query()
        user_links = user_songs_table.search(UserSong.owner == owner)
        video_ids = [link.get('videoId') for link in user_links if link.get('videoId')]
        tracks = [s for s in songs_table.all() if s.get('videoId') in video_ids] if video_ids else []

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
            for inst in track.get('instruments', []):
                tags[inst] = tags.get(inst, {'type': 'instrument', 'count': 0})
                tags[inst]['count'] += 1

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
    with _db_lock:
        if db is None:
            db = init_db()
        history_table = db.table('history')
        return {r['playlistId']: r for r in history_table.all()}


# --- Enrichment Task State ---

def save_task_state(task_id: str, state: dict, db: TinyDB = None) -> None:
    """Persist enrichment task state to database."""
    with _db_lock:
        if db is None:
            db = init_db()
        tasks_table = db.table('tasks')
        Task = Query()
        record = {"task_id": task_id, **state}
        tasks_table.upsert(record, Task.task_id == task_id)


def get_task_state(task_id: str, db: TinyDB = None) -> dict | None:
    """Retrieve enrichment task state by task_id."""
    with _db_lock:
        if db is None:
            db = init_db()
        tasks_table = db.table('tasks')
        Task = Query()
        results = tasks_table.search(Task.task_id == task_id)
        return results[0] if results else None


def get_all_active_tasks(db: TinyDB = None) -> dict:
    """Get all active (pending/running) enrichment tasks. Returns dict keyed by task_id."""
    with _db_lock:
        if db is None:
            db = init_db()
        tasks_table = db.table('tasks')
        Task = Query()
        active = tasks_table.search(
            (Task.status == "pending") | (Task.status == "running")
        )
        return {t['task_id']: t for t in active}

