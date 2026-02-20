"""Song Shake API — FastAPI application entry point.

This is the thin app shell that configures middleware and includes route modules.
All endpoint logic lives in routes_*.py modules.
"""

import os

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dotenv import load_dotenv
from song_shake.platform.logging_config import configure_logging

load_dotenv()
configure_logging()

from song_shake.features.auth.routes import router as auth_router
from song_shake.features.songs.routes_playlists import router as playlists_router
from song_shake.features.songs.routes import router as songs_router
from song_shake.features.jobs.routes import router as jobs_router

app = FastAPI(title="Song Shake API")

# CORS — locked to production domain when ENV=production
_cors_origins_raw = os.getenv("CORS_ORIGINS", "")
if _cors_origins_raw:
    cors_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]
else:
    cors_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include route modules
app.include_router(auth_router)
app.include_router(playlists_router, prefix="/api")
app.include_router(songs_router, prefix="/api")
app.include_router(jobs_router, prefix="/api")

if __name__ == "__main__":
    uvicorn.run("song_shake.api:app", host="0.0.0.0", port=8000, reload=True)
