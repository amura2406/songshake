import requests
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, RedirectResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from urllib.parse import urlencode
from urllib.parse import urlencode
import uvicorn
import os
import json
import time
import asyncio
from ytmusicapi import YTMusic, setup
from ytmusicapi.auth.oauth import RefreshingToken
from song_shake import storage, enrichment, playlist, auth
from google import genai
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

# State
enrichment_tasks: Dict[str, Dict[str, Any]] = {}
oauth_states: Dict[str, Any] = {} # Store device codes etc.

class LoginRequest(BaseModel):
    headers_raw: Optional[str] = None

class OAuthInitRequest(BaseModel):
    client_id: Optional[str] = None
    client_secret: Optional[str] = None

class OAuthPollRequest(BaseModel):
    device_code: str
    client_id: Optional[str] = None
    client_secret: Optional[str] = None

class PlaylistResponse(BaseModel):
    playlistId: str
    title: str
    thumbnails: List[Dict[str, Any]]
    count: Optional[Any] = None
    description: Optional[str] = None
    last_processed: Optional[str] = None
    last_status: Optional[str] = None

class EnrichmentRequest(BaseModel):
    playlist_id: str
    owner: str = "web_user"
    api_key: Optional[str] = None

class Song(BaseModel):
    videoId: str
    title: str
    artists: str
    album: Optional[str] = None
    thumbnails: List[Dict[str, Any]] = []
    genres: List[str] = []
    moods: List[str] = []
    status: str
    error_message: Optional[str] = None
    url: Optional[str] = None
    owner: Optional[str] = None



def get_ytmusic():
    try:
        return auth.get_ytmusic()
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")

@app.get("/auth/logout")
def logout():
    if os.path.exists("oauth.json"):
        os.remove("oauth.json")
    return {"status": "logged_out"}

@app.get("/auth/me")
def get_current_user():
    if not os.path.exists("oauth.json"):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        # Try to get user info via Google API
        with open("oauth.json") as f:
            tokens = json.load(f)
        
        token = tokens.get("access_token")
        if not token:
             raise HTTPException(status_code=401, detail="No access token")
             
        headers = {"Authorization": f"Bearer {token}"}
        
        # 1. Try Channel Info (best for stable ID)
        res = requests.get(
            "https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true",
            headers=headers
        )
        
        user_id = "web_user"
        name = "Authenticated User"
        thumb = None
        
        if res.status_code == 200:
            data = res.json()
            if data.get("items"):
                item = data["items"][0]
                user_id = item["id"]  # Unique Channel ID
                snippet = item["snippet"]
                name = snippet.get("title", "YouTube User")
                thumb = snippet["thumbnails"]["default"]["url"]
                return {
                    "id": user_id,
                    "name": name,
                    "thumbnail": thumb,
                    "authenticated": True
                }
        
        # 2. If Channel fails (Channel-less), try UserInfo for name/email
        # This requires 'profile' or 'email' scope, which we might not have, but let's try.
        try:
            res2 = requests.get("https://www.googleapis.com/oauth2/v2/userinfo", headers=headers)
            if res2.status_code == 200:
                uinfo = res2.json()
                # Use email as ID if available, otherwise ID
                user_id = uinfo.get("id") or uinfo.get("email") or "web_user"
                name = uinfo.get("name") or uinfo.get("email") or "User"
                thumb = uinfo.get("picture")
                return {
                    "id": user_id,
                    "name": name,
                    "thumbnail": thumb,
                    "authenticated": True
                }
        except:
            pass
            
        # 3. Fallback
        return {
            "id": "web_user",
            "name": "Authenticated User (No Channel)", 
            "thumbnail": None,
            "authenticated": True,
            "note": "Could not fetch channel profile"
        }
            
    except Exception as e:
        print(f"Error fetching user: {e}")
        return {"authenticated": False}
    return {"authenticated": False}

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
        is_json = False
        try:
            json.loads(request.headers_raw)
            is_json = True
        except json.JSONDecodeError:
            pass
            
        if is_json:
            with open("oauth.json", "w") as f:
                f.write(request.headers_raw)
        else:
            setup(filepath="oauth.json", headers_raw=request.headers_raw)
        
        YTMusic("oauth.json")
        return {"status": "success"}
    except Exception as e:
        if os.path.exists("oauth.json"):
            os.remove("oauth.json")
        raise HTTPException(status_code=400, detail=f"Invalid headers: {str(e)}")

@app.get("/auth/config")
def auth_config():
    load_dotenv()
    has_env = bool(os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET"))
    return {"use_env": has_env}

@app.get("/auth/google/login")
def google_auth_login():
    load_dotenv()
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    if not client_id:
        raise HTTPException(status_code=400, detail="GOOGLE_CLIENT_ID not set in .env")
    
    redirect_uri = "http://localhost:8000/auth/google/callback"
    scope = "https://www.googleapis.com/auth/youtube"
    
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scope,
        "access_type": "offline",
        "prompt": "consent"
    }
    url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return RedirectResponse(url)

@app.get("/auth/google/callback")
def google_auth_callback(code: str):
    load_dotenv()
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_uri = "http://localhost:8000/auth/google/callback"
    
    if not client_id or not client_secret:
        raise HTTPException(status_code=400, detail="Credentials not set in .env")

    # Exchange code for token
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri
    }
    
    try:
        response = requests.post(token_url, data=data)
        response.raise_for_status()
        tokens = response.json()
        
        tokens['expires_at'] = int(time.time()) + tokens.get('expires_in', 3600)
        
        with open("oauth.json", "w") as f:
            json.dump(tokens, f)
            
        return RedirectResponse("http://localhost:5173/")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {e}")

@app.post("/auth/google/init")
def google_auth_init(request: OAuthInitRequest):
    try:
        load_dotenv()
        client_id = request.client_id or os.getenv("GOOGLE_CLIENT_ID")
        client_secret = request.client_secret or os.getenv("GOOGLE_CLIENT_SECRET")
        
        if not client_id or not client_secret:
             raise HTTPException(status_code=400, detail="Client ID and Secret required (not found in request or env)")

        creds = OAuthCredentials(client_id=client_id, client_secret=client_secret)
        code = creds.get_code()
        # Store state if needed, but client sends device_code back for polling
        return code
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/auth/google/poll")
def google_auth_poll(request: OAuthPollRequest):
    try:
        load_dotenv()
        client_id = request.client_id or os.getenv("GOOGLE_CLIENT_ID")
        client_secret = request.client_secret or os.getenv("GOOGLE_CLIENT_SECRET")
        
        if not client_id or not client_secret:
             raise HTTPException(status_code=400, detail="Client ID and Secret required")

        creds = OAuthCredentials(client_id=client_id, client_secret=client_secret)
        # Verify code
        token = creds.token_from_code(request.device_code)
        
        # If we are here, we got the token!
        # Create a RefreshingToken to get the full structure and save it
        # We need to reconstruct the token dict expected by RefreshingToken
        # The token_from_code returns something like {'access_token': ..., 'expires_in': ..., 'refresh_token': ...}
        
        # We need to save it as oauth.json
        # RefreshingToken.store_token expects a path.
        # check token structure
        
        # We can just Dump it to json. YTMusic accepts file path or dict (if valid json keys)
        # But YTMusic usually expects headers dict for 'browser' auth, OR a specific json for 'oauth'.
        # For 'oauth', it needs 'refresh_token', 'client_id', 'client_secret'.
        
        final_token = token.copy()
        final_token['client_id'] = client_id
        final_token['client_secret'] = client_secret
        
        # Wait, ytmusicapi.setup_oauth returns a RefreshingToken which has .as_json()
        # Let's try to mimic that.
        ref_token = RefreshingToken(credentials=creds, **token)
        ref_token.update(ref_token.as_dict()) # updates expires_at
        
        # We need to save this to oauth.json
        # The json format for oauth includes token_type, access_token, refresh_token, scope, expires_at, expires_in
        # AND It should probably be passed to YTMusic("oauth.json")
        
        with open("oauth.json", "w") as f:
            f.write(ref_token.as_json())
            
        return {"status": "success"}
        
    except Exception as e:
        # Check if it's just pending
        err_str = str(e).lower()
        if "authorization_pending" in err_str or "precondition_required" in err_str:
            return {"status": "pending"}
        # ytmusicapi might raise specific exceptions
        if "authorization_pending" in str(e): # check actual string if possible
             return {"status": "pending"}
             
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/playlists", response_model=List[PlaylistResponse])
def get_playlists(yt: YTMusic = Depends(get_ytmusic)):
    try:
        playlists = []
        try:
            playlists = yt.get_library_playlists(limit=50)
        except Exception as e:
            print(f"DEBUG: get_library_playlists failed: {e}")
            # Fallback to Data API
            try:
                print("Attempting Data API fallback...")
                playlists = auth.get_data_api_playlists(yt, limit=50)
            except Exception as e2:
                print(f"Data API fallback failed: {e2}")
                pass
        
        # Manually add Liked Music if not present
        has_liked = any(p.get('playlistId') == 'LM' or p.get('title') == 'Your Likes' for p in playlists)
        
        if not has_liked:
            liked_music = {
                "playlistId": "LM",
                "title": "Liked Music",
                "thumbnails": [{"url": "https://www.gstatic.com/youtube/media/ytm/images/pbg/liked-music-@576.png", "width": 576, "height": 576}],
                "count": "Auto", 
                "description": "Your liked songs"
            }
            playlists.insert(0, liked_music)
        
        # Merge with history
        try:
            history = storage.get_all_history()
            print(f"DEBUG: History keys: {list(history.keys())}")
            for p in playlists:
                pid = p.get('playlistId')
                if pid in history:
                    p['last_processed'] = history[pid].get('last_processed')
                    p['last_status'] = history[pid].get('status')
                    print(f"DEBUG: Merged history for {pid}: {p['last_processed']}")
                else:
                    # check if string/int mismatch?
                    pass
        except Exception as e:
            print(f"Error merging history: {e}")
            
        return playlists
    except Exception as e:
        # If 401, trying to refresh token?
        # YTMusic handles refresh automatically if initialized with oauth.json
        print(f"DEBUG: get_playlists failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

def process_enrichment(task_id: str, playlist_id: str, owner: str, api_key: str):
    try:
        print(f"DEBUG: Starting enrichment for playlist={playlist_id} owner={owner} task={task_id}")
        enrichment_tasks[task_id]["status"] = "running"
        enrichment_tasks[task_id]["message"] = "Fetching tracks..."
        enrichment_tasks[task_id]["tokens"] = 0
        enrichment_tasks[task_id]["cost"] = 0
        
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
                filename = enrichment.download_track(video_id)
                metadata = enrichment.enrich_track(client, filename, title, artists, tracker)
                
                if os.path.exists(filename):
                    os.remove(filename)
                
                is_error = bool(metadata.get('error'))
                track_data = {
                    "videoId": video_id,
                    "title": title,
                    "artists": artists,
                    "album": track.get('album', {}).get('name') if track.get('album') else None,
                    "thumbnails": track.get('thumbnails', []),
                    "genres": metadata.get('genres', []),
                    "moods": metadata.get('moods', []),
                    "status": "error" if is_error else "success",
                    "success": not is_error,
                    "error_message": metadata.get('error'),
                    "url": f"https://music.youtube.com/watch?v={video_id}",
                    "owner": owner
                }
                
                storage.save_track(db, track_data)
                results.append(track_data)
                
                # Update task immediately so stream sees it
                enrichment_tasks[task_id]["results"] = results
                enrichment_tasks[task_id]["tokens"] = getattr(tracker, 'input_tokens', 0) + getattr(tracker, 'output_tokens', 0)
                enrichment_tasks[task_id]["cost"] = tracker.get_cost() if hasattr(tracker, 'get_cost') else 0
                
            except Exception as e:
                print(f"Error processing {title}: {e}")
                err_track_data = {
                    "videoId": video_id,
                    "title": title,
                    "artists": artists,
                    "album": track.get('album', {}).get('name') if track.get('album') else None,
                    "thumbnails": track.get('thumbnails', []),
                    "genres": [],
                    "moods": [],
                    "status": "error",
                    "success": False,
                    "error_message": str(e),
                    "url": f"https://music.youtube.com/watch?v={video_id}",
                    "owner": owner
                }
                storage.save_track(db, err_track_data)
                results.append(err_track_data)
                enrichment_tasks[task_id]["results"] = results
        
        enrichment_tasks[task_id]["status"] = "completed"
        enrichment_tasks[task_id]["message"] = "Enrichment complete"
        enrichment_tasks[task_id]["current"] = len(tracks)
        enrichment_tasks[task_id]["tokens"] = getattr(tracker, 'input_tokens', 0) + getattr(tracker, 'output_tokens', 0)
        enrichment_tasks[task_id]["cost"] = tracker.get_cost() if hasattr(tracker, 'get_cost') else 0
        
        # Save history on success
        try:
            print(f"DEBUG: Saving history for {playlist_id} owner={owner}")
            from datetime import datetime
            storage.save_enrichment_history(
                playlist_id, 
                owner, 
                {
                    'timestamp': datetime.now().isoformat(),
                    'item_count': len(results),
                    'status': 'completed'
                },
                db
            )
        except Exception as h_err:
            print(f"Failed to save history: {h_err}")

    except Exception as e:
        enrichment_tasks[task_id]["status"] = "error"
        enrichment_tasks[task_id]["message"] = str(e)
        
        # Save error history too?
        try:
            from datetime import datetime
            storage.save_enrichment_history(
                playlist_id, 
                owner, 
                {
                    'timestamp': datetime.now().isoformat(),
                    'item_count': 0,
                    'status': 'error',
                    'error': str(e)
                },
                db
            )
        except:
            pass

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

@app.get("/enrichment/status/{task_id}")
def get_enrichment_status(task_id: str):
    if task_id not in enrichment_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return enrichment_tasks[task_id]

@app.get("/enrichment/stream/{task_id}")
async def stream_enrichment_status(task_id: str):
    if task_id not in enrichment_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
        
    async def event_generator():
        last_current = -1
        last_status = ""
        
        while True:
            if task_id not in enrichment_tasks:
                yield f"event: error\ndata: {json.dumps({'error': 'Task lost'})}\n\n"
                break
                
            task = enrichment_tasks[task_id]
            
            # Yield event if something changed or just periodically
            # SSE clients usually expect keep-alive
            
            data = json.dumps({
                "status": task["status"],
                "total": task["total"],
                "current": task["current"],
                "message": task["message"],
                "tokens": task.get("tokens", 0),
                "cost": task.get("cost", 0)
                # Don't send full results every time if big, but for now it's fine
            })
            
            yield f"data: {data}\n\n"
            
            if task["status"] in ["completed", "error"]:
                # Send one last time then close
                break
            
            await asyncio.sleep(0.5)
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/songs", response_model=List[Song])
def get_songs(owner: str = "web_user", skip: int = 0, limit: int = 50, tags: Optional[str] = None):
    print(f"DEBUG: get_songs requested for owner='{owner}' skip={skip} limit={limit} tags='{tags}'")
    all_tracks = storage.get_all_tracks(owner=owner)
    
    if tags:
        filter_tags = set([t.strip() for t in tags.split(',') if t.strip()])
        filtered_tracks = []
        for track in all_tracks:
            track_tags = set(track.get('genres', []) + track.get('moods', []))
            if getattr(track, 'success', track.get('status') == 'success'):
                track_tags.add('Success')
            else:
                track_tags.add('Failed')

            if filter_tags.issubset(track_tags):
                filtered_tracks.append(track)
        all_tracks = filtered_tracks
        
    print(f"DEBUG: returning {len(all_tracks)} tracks after filtering")
    return all_tracks[skip : skip + limit]

class TagResponse(BaseModel):
    name: str
    type: str
    count: int

@app.get("/tags", response_model=List[TagResponse])
def get_tags(owner: str = "web_user"):
    return storage.get_tags(owner=owner)

if __name__ == "__main__":
    uvicorn.run("song_shake.api:app", host="0.0.0.0", port=8000, reload=True)

