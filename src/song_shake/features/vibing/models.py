"""Pydantic models for the Playlist Vibing feature."""

from enum import Enum

from pydantic import BaseModel, Field


class VibeRecipe(str, Enum):
    """Available AI playlist recipes."""

    NEGLECTED_GEMS = "neglected_gems"
    ENERGY_ZONES = "energy_zones"
    AESTHETIC_UNIVERSES = "aesthetic_universes"
    VOCAL_DIVIDE = "vocal_divide"
    DJ_SET_ARC = "dj_set_arc"


class VibeRequest(BaseModel):
    """Request body for generating a vibe playlist."""

    track_count: int = Field(
        default=49,
        ge=5,
        le=149,
        description="Number of tracks to curate (excluding the seed).",
    )
    recipe: VibeRecipe = Field(
        default=VibeRecipe.NEGLECTED_GEMS,
        description="The recipe strategy for playlist generation.",
    )


# --- Gemini response schemas ---


class GeminiCurationResult(BaseModel):
    """Structured output schema for single-playlist Gemini response.

    Used by "Neglected Gems" recipe.
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


class GeminiPlaylistEntry(BaseModel):
    """A single playlist within a multi-playlist Gemini response."""

    candidate_titles: list[str] = Field(
        description=(
            "A list of 20 creative, catchy candidate titles for this playlist. "
            "Each title should be distinct and evocative. The app will pick "
            "the first one that hasn't been used before."
        )
    )
    description: str = Field(
        description=(
            "A short 1-2 sentence description explaining this playlist's "
            "vibe and what ties the tracks together."
        )
    )
    curated_video_ids: list[str] = Field(
        description="List of videoIds selected from the catalog for this playlist."
    )


class GeminiMultiPlaylistResult(BaseModel):
    """Structured output schema for multi-playlist Gemini response.

    Used by Energy Zones, Aesthetic Universes, Vocal Divide, DJ Set Arc.
    """

    playlists: list[GeminiPlaylistEntry] = Field(
        description="List of curated playlists, each with a title, description, and track list."
    )


# --- API response models ---


class VibePlaylistResponse(BaseModel):
    """API response model for a single vibe playlist."""

    id: str
    owner: str
    title: str
    description: str = ""
    seed_video_id: str = ""
    seed_title: str = ""
    seed_artist: str = ""
    video_ids: list[str]
    status: str  # "draft" | "synced"
    youtube_playlist_id: str | None = None
    created_at: str
    track_count: int = 0
    recipe: str = "neglected_gems"
    batch_id: str | None = None


class VibePlaylistTrack(BaseModel):
    """Lightweight track info returned in playlist detail."""

    videoId: str
    title: str
    artists: list[dict] | str = []
    album: dict | str | None = None
    year: str | None = None
    genres: list[str] = []
    moods: list[str] = []
    instruments: list[str] = []
    bpm: int | None = None
    thumbnails: list[dict] = []
    is_seed: bool = False


class VibePlaylistDetailResponse(BaseModel):
    """API response model for playlist detail with full track info."""

    id: str
    owner: str
    title: str
    description: str = ""
    seed_video_id: str = ""
    status: str
    youtube_playlist_id: str | None = None
    created_at: str
    tracks: list[VibePlaylistTrack] = []
    recipe: str = "neglected_gems"
    batch_id: str | None = None
