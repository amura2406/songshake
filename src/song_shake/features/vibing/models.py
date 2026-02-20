"""Pydantic models for the Playlist Vibing feature."""

from pydantic import BaseModel, Field


class VibeRequest(BaseModel):
    """Request body for generating a vibe playlist."""

    track_count: int = Field(
        default=49,
        ge=5,
        le=149,
        description="Number of tracks to curate (excluding the seed).",
    )


class GeminiCurationResult(BaseModel):
    """Structured output schema for Gemini AI DJ response.

    Used as ``response_schema`` so the model returns a parsed object.
    """

    curated_video_ids: list[str] = Field(
        description="List of videoIds selected from the catalog."
    )
    generated_playlist_title: str = Field(
        description="A creative title for the playlist."
    )
    description: str = Field(
        description=(
            "A short 1-2 sentence description of the playlist's vibe, "
            "explaining the musical theme, mood progression, and why "
            "these tracks work together. Written for the listener."
        )
    )


class VibePlaylistResponse(BaseModel):
    """API response model for a single vibe playlist."""

    id: str
    owner: str
    title: str
    description: str = ""
    seed_video_id: str
    seed_title: str = ""
    seed_artist: str = ""
    video_ids: list[str]
    status: str  # "draft" | "synced"
    youtube_playlist_id: str | None = None
    created_at: str
    track_count: int = 0


class VibePlaylistTrack(BaseModel):
    """Lightweight track info returned in playlist detail."""

    videoId: str
    title: str
    artists: list[dict] | str = []
    album: dict | str | None = None
    year: str | None = None
    genres: list[str] = []
    moods: list[str] = []
    bpm: int | None = None
    thumbnails: list[dict] = []
    is_seed: bool = False


class VibePlaylistDetailResponse(BaseModel):
    """API response model for playlist detail with full track info."""

    id: str
    owner: str
    title: str
    description: str = ""
    seed_video_id: str
    status: str
    youtube_playlist_id: str | None = None
    created_at: str
    tracks: list[VibePlaylistTrack] = []
