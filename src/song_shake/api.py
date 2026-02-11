from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn
import os
import json
from ytmusicapi import YTMusic
from song_shake import storage, enrichment, playlist
from google import genai
from google.genai import types
from dotenv import load_dotenv

app = FastAPI(title="Song Shake API")

# Allow CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For dev only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# State for progress tracking
# Format: { task_id: { "status": "running"|"completed"|"error", "total": int, "current": int, "message": str, "results": [] } }
enrichment_tasks: Dict[str, Dict[str, Any]] = {}

class LoginRequest(BaseModel):
    headers_raw: Optional[str] = None
    # Potentially OAuth code/token in future

class PlaylistResponse(BaseModel):
    playlistId: str
    title: str
    thumbnails: List[Dict[str, Any]]
    count: Optional[Any] = None
    description: Optional[str] = None

class EnrichmentRequest(BaseModel):
    playlist_id: str
    owner: str = "web_user" # Default owner for web
    api_key: Optional[str] = None # Google API Key

class Song(BaseModel):
    videoId: str
    title: str
    artists: str
    album: Optional[str] = None
    genres: List[str] = []
    moods: List[str] = []
    status: str
    error_message: Optional[str] = None
    url: Optional[str] = None
    owner: Optional[str] = None

def get_ytmusic():
    if not os.path.exists("oauth.json"):
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        return YTMusic("oauth.json")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")

@app.get("/auth/status")
def auth_status():
    if os.path.exists("oauth.json"):
        return {"authenticated": True}
    return {"authenticated": False}

@app.post("/auth/login")
def login(request: LoginRequest):
    if not request.headers_raw:
        raise HTTPException(status_code=400, detail="Headers required")
    
    try:
        # Try to parse and save headers using ytmusicapi logic or our own
        # Reusing auth.py logic or similar
        # For now, let's just use YTMusic.setup
        # It takes headers_raw and creates the file
        YTMusic.setup(filepath="oauth.json", headers_raw=request.headers_raw)
        
        # Verify
        YTMusic("oauth.json")
        return {"status": "success"}
    except Exception as e:
        if os.path.exists("oauth.json"):
            os.remove("oauth.json")
        raise HTTPException(status_code=400, detail=f"Invalid headers: {str(e)}")

@app.get("/playlists", response_model=List[PlaylistResponse])
def get_playlists(yt: YTMusic = Depends(get_ytmusic)):
    try:
        playlists = yt.get_library_playlists(limit=50)
        return playlists
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def process_enrichment(task_id: str, playlist_id: str, owner: str, api_key: str):
    try:
        enrichment_tasks[task_id]["status"] = "running"
        enrichment_tasks[task_id]["message"] = "Fetching tracks..."
        
        tracks = playlist.get_tracks(playlist_id)
        if not tracks:
             enrichment_tasks[task_id]["status"] = "error"
             enrichment_tasks[task_id]["message"] = "No tracks found"
             return

        enrichment_tasks[task_id]["total"] = len(tracks)
        client = genai.Client(api_key=api_key)
        tracker = enrichment.TokenTracker()
        
        results = []
        db = storage.init_db()

        for i, track in enumerate(tracks):
            enrichment_tasks[task_id]["current"] = i
            title = track.get('title', 'Unknown')
            artists = ", ".join([a['name'] for a in track.get('artists', [])])
            enrichment_tasks[task_id]["message"] = f"Processing: {title} - {artists}"
            
            video_id = track.get('videoId')
            if not video_id:
                continue

            try:
                # Reuse logic from enrichment.py but we need it to be importable/callable per track
                # OR we copy-paste logic here.
                # Ideally refactor enrichment.py to expose 'process_single_track'
                # For now, let's copy the core logic or call `enrichment.download_track` and `enrichment.enrich_track`
                
                filename = enrichment.download_track(video_id)
                metadata = enrichment.enrich_track(client, filename, title, artists, tracker)
                
                if os.path.exists(filename):
                    os.remove(filename)
                
                track_data = {
                    "videoId": video_id,
                    "title": title,
                    "artists": artists,
                    "album": track.get('album', {}).get('name') if track.get('album') else None,
                    "genres": metadata.get('genres', []),
                    "moods": metadata.get('moods', []),
                    "status": "error" if metadata.get('error') else "success",
                    "error_message": metadata.get('error'),
                    "url": f"https://music.youtube.com/watch?v={video_id}",
                    "owner": owner
                }
                
                storage.save_track(db, track_data)
                results.append(track_data)
                
            except Exception as e:
                print(f"Error processing {title}: {e}")
        
        enrichment_tasks[task_id]["status"] = "completed"
        enrichment_tasks[task_id]["message"] = "Enrichment complete"
        enrichment_tasks[task_id]["results"] = results # Optional: might be too big
        enrichment_tasks[task_id]["current"] = len(tracks)
        
    except Exception as e:
        enrichment_tasks[task_id]["status"] = "error"
        enrichment_tasks[task_id]["message"] = str(e)

@app.post("/enrichment")
def start_enrichment(request: EnrichmentRequest, background_tasks: BackgroundTasks):
    load_dotenv()
    api_key = request.api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=400, detail="API Key required")
    
    task_id = f"{request.playlist_id}_{os.urandom(4).hex()}"
    enrichment_tasks[task_id] = {
        "status": "pending",
        "total": 0,
        "current": 0,
        "message": "Initializing...",
        "results": []
    }
    
    background_tasks.add_task(process_enrichment, task_id, request.playlist_id, request.owner, api_key)
    return {"task_id": task_id}

@app.get("/enrichment/{task_id}")
def get_enrichment_status(task_id: str):
    if task_id not in enrichment_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return enrichment_tasks[task_id]

@app.get("/songs", response_model=List[Song])
def get_songs(owner: str = "web_user", skip: int = 0, limit: int = 50):
    all_tracks = storage.get_all_tracks(owner=owner)
    # Basic pagination in memory (TinyDB doesn't support skip/limit natively efficiently)
    start = skip
    end = skip + limit
    return all_tracks[start:end]

if __name__ == "__main__":
    uvicorn.run("song_shake.api:app", host="0.0.0.0", port=8000, reload=True)
