"""Gemini AI DJ adapter — curates playlists via google-genai SDK."""

import json
import os

from google import genai

from song_shake.features.vibing.logic import extract_artist_string, minify_catalog, pre_sort_by_bpm
from song_shake.features.vibing.models import (
    GeminiCurationResult,
    GeminiMultiPlaylistResult,
    VibeRecipe,
)
from song_shake.platform.logging_config import get_logger

logger = get_logger(__name__)

# --- Single-playlist prompt (Neglected Gems) ---

NEGLECTED_GEMS_SYSTEM = (
    "You are an expert DJ and music curator. I am providing a 'Seed Track' and "
    "a JSON catalog of available tracks. Select exactly {track_count} tracks "
    "from the catalog that create the most musically cohesive and aesthetically "
    "pleasing playlist around the Seed Track. Pay attention to BPM flow, genre "
    "blending, and mood progression. Return ONLY videoIds that exist in the "
    "provided catalog. Also provide a short 1-2 sentence description explaining "
    "the playlist's vibe: what musical thread ties these tracks together, and "
    "what journey the listener will experience."
)

# --- Multi-playlist prompts ---

ENERGY_ZONES_SYSTEM = (
    "You are an expert DJ and music curator. I am providing a JSON catalog of "
    "tracks sorted by BPM. Create EXACTLY 3 playlists based on physiological "
    "energy levels. Each playlist should have at most {per_playlist_limit} tracks. "
    "A track must appear in AT MOST ONE playlist. "
    "Return ONLY videoIds that exist in the provided catalog.\n\n"
    "The 3 playlists MUST be:\n"
    "1. 'Deep Focus / Night Drive' — BPM below 110, moods like Atmospheric, "
    "Melancholic, Relaxed, Calm, Dreamy, Peaceful, or similar chill moods.\n"
    "2. 'The Daily Groove' — BPM between 110 and 124, moods like Groovy, "
    "Danceable, Funky, Catchy, or similar feel-good moods.\n"
    "3. 'Adrenaline Spike' — BPM above 125, moods like Energetic, Intense, "
    "Euphoric, Aggressive, Bold, or similar high-energy moods.\n\n"
    "For each playlist, provide 20 creative and distinct candidate titles "
    "(the app will pick the first unused one). "
    "Include a short 1-2 sentence description for each."
)

AESTHETIC_UNIVERSES_SYSTEM = (
    "You are an expert DJ and music curator. I am providing a JSON catalog of "
    "tracks with their genres and instruments. Group tracks into hyper-specific "
    "'sonic universes' based on overlapping genres AND instruments. "
    "Create between 3 and 12 playlists depending on the diversity of the library. "
    "Each playlist should have at most {per_playlist_limit} tracks. "
    "A track must appear in AT MOST ONE playlist. "
    "Return ONLY videoIds that exist in the provided catalog.\n\n"
    "Example universe types (adapt to the actual data):\n"
    "- 'The Neon Grid': Retrowave, Synth-pop + Synthesizer, Drum machine\n"
    "- 'Mainstage Festival': EDM, House, Trance + Lead synth, Claps\n"
    "- 'Organic Indie Lounge': Indie pop, Dream-pop + Acoustic guitar, Bass guitar\n"
    "- 'Hip-Hop Vault': Hip-hop, Drill + Drums, Bass synth, Turntables\n"
    "- 'Classical Crossover': Classical, Cinematic + Strings, Piano, Orchestra\n\n"
    "For each universe, provide 20 vivid, imaginative candidate titles "
    "(the app will pick the first unused one) and a short 1-2 sentence "
    "description. Only create universes that have enough matching tracks."
)

VOCAL_DIVIDE_SYSTEM = (
    "You are an expert DJ and music curator. I am providing a JSON catalog of "
    "tracks with their instruments and vocalType. Divide the catalog into "
    "EXACTLY 2 playlists based on vocal presence. Each playlist should have "
    "at most {per_playlist_limit} tracks. "
    "A track must appear in AT MOST ONE playlist. "
    "Return ONLY videoIds that exist in the provided catalog.\n\n"
    "The 2 playlists MUST be:\n"
    "1. A 'Vocals' playlist — tracks with human voice (vocalType='Vocals' or "
    "'Vocals' in instruments). Group tracks that have similar moods and "
    "compatible BPMs so they flow well together.\n"
    "2. An 'Instrumental' playlist — tracks without vocals (vocalType='Instrumental' "
    "or no 'Vocals' in instruments). Also group by mood/BPM cohesion.\n\n"
    "For each playlist, provide 20 creative and distinct candidate titles "
    "(the app will pick the first unused one) and a short 1-2 sentence description."
)

DJ_SET_ARC_SYSTEM = (
    "You are an expert DJ building a live 2.5-hour DJ set. I am providing a "
    "JSON catalog of tracks. Select and ORDER exactly 50 tracks to create a "
    "narrative arc that mimics a real DJ performance. "
    "A track must appear AT MOST ONCE. "
    "Return ONLY videoIds that exist in the provided catalog.\n\n"
    "The narrative arc MUST follow these phases:\n"
    "- Tracks 1–10 (The Warm-up): Mid-tempo (90-110 BPM), moods: Groovy, Dreamy, "
    "Relaxed. Ease the listener in.\n"
    "- Tracks 11–35 (The Peak): Higher BPM (120-130 BPM), genres: EDM, House, "
    "Dance. Moods: Energetic, Danceable, Euphoric. Build the energy.\n"
    "- Tracks 36–45 (The Climax): Maximum BPM (130+), genres: Drum and bass, "
    "Future bass, Dubstep, Trance. Moods: Intense, Aggressive, Euphoric.\n"
    "- Tracks 46–50 (The Cool Down): Low BPM (< 100), moods: Calm, Melancholic, "
    "Cinematic, Atmospheric. Bring the listener down gently.\n\n"
    "Create a single playlist. Provide 20 creative and distinct candidate titles "
    "that capture the journey (e.g. 'Midnight Odyssey', 'Neon Horizon Set'). "
    "The app will pick the first unused one. Include a description explaining "
    "the narrative arc."
)

MODEL_ID = "gemini-3.1-pro-preview"

# Gemini 3.1 Pro Preview pricing (USD per 1M tokens)
PRICE_INPUT_PER_1M = 1.25
PRICE_OUTPUT_PER_1M = 10.00


def _get_client() -> genai.Client:
    """Create a Gemini client using the API key from environment."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY environment variable is not set.")
    return genai.Client(api_key=api_key)


def _calculate_usage(response) -> dict:
    """Extract token usage and cost from a Gemini response."""
    input_tokens = 0
    output_tokens = 0
    if response.usage_metadata:
        input_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
        output_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0

    cost = (
        (input_tokens / 1_000_000) * PRICE_INPUT_PER_1M
        + (output_tokens / 1_000_000) * PRICE_OUTPUT_PER_1M
    )
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost": round(cost, 6),
    }


def curate_playlist(
    seed_track: dict,
    remaining_tracks: list[dict],
    track_count: int = 49,
) -> tuple[GeminiCurationResult, dict]:
    """Call Gemini to curate a single playlist around the seed track.

    Used by the "Neglected Gems" recipe.

    Returns:
        A tuple of (GeminiCurationResult, ai_usage_dict).
    """
    client = _get_client()

    catalog = minify_catalog(remaining_tracks)
    seed_info = {
        "videoId": seed_track["videoId"],
        "title": seed_track.get("title", ""),
        "artist_names": extract_artist_string(seed_track),
        "genres": seed_track.get("genres", []),
        "moods": seed_track.get("moods", []),
        "bpm": seed_track.get("bpm"),
    }

    user_prompt = (
        f"Seed Track:\n{json.dumps(seed_info, ensure_ascii=False)}\n\n"
        f"Available Catalog ({len(catalog)} tracks):\n"
        f"{json.dumps(catalog, ensure_ascii=False)}"
    )

    system_text = NEGLECTED_GEMS_SYSTEM.format(track_count=track_count)

    logger.info(
        "gemini_curate_started",
        model=MODEL_ID,
        recipe="neglected_gems",
        seed_title=seed_track.get("title"),
        catalog_size=len(catalog),
        requested_count=track_count,
    )

    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=user_prompt,
            config=genai.types.GenerateContentConfig(
                system_instruction=system_text,
                response_mime_type="application/json",
                response_schema=GeminiCurationResult,
            ),
        )

        result = response.parsed
        if result is None:
            raise RuntimeError(
                f"Gemini returned unparseable response: {response.text}"
            )

        ai_usage = _calculate_usage(response)

        logger.info(
            "gemini_curate_success",
            recipe="neglected_gems",
            playlist_title=result.generated_playlist_title,
            curated_count=len(result.curated_video_ids),
            **ai_usage,
        )
        return result, ai_usage

    except Exception as exc:
        logger.error("gemini_curate_failed", recipe="neglected_gems", error=str(exc))
        raise RuntimeError(f"Gemini curation failed: {exc}") from exc


def curate_multi_playlist(
    recipe: VibeRecipe,
    tracks: list[dict],
    track_count: int = 49,
) -> tuple[GeminiMultiPlaylistResult, dict]:
    """Call Gemini to curate multiple playlists based on a recipe.

    Used by Energy Zones, Aesthetic Universes, Vocal Divide, DJ Set Arc.

    Args:
        recipe: The selected recipe strategy.
        tracks: Full track dicts from storage (not yet minified).
        track_count: Per-playlist track limit.

    Returns:
        A tuple of (GeminiMultiPlaylistResult, ai_usage_dict).

    Raises:
        RuntimeError: If Gemini call fails.
        ValueError: If recipe is unknown.
    """
    client = _get_client()

    catalog = minify_catalog(tracks)

    # Recipe-specific pre-processing and prompt selection
    if recipe == VibeRecipe.ENERGY_ZONES:
        catalog = pre_sort_by_bpm(catalog)
        system_text = ENERGY_ZONES_SYSTEM.format(per_playlist_limit=track_count)
    elif recipe == VibeRecipe.AESTHETIC_UNIVERSES:
        system_text = AESTHETIC_UNIVERSES_SYSTEM.format(per_playlist_limit=track_count)
    elif recipe == VibeRecipe.VOCAL_DIVIDE:
        system_text = VOCAL_DIVIDE_SYSTEM.format(per_playlist_limit=track_count)
    elif recipe == VibeRecipe.DJ_SET_ARC:
        # DJ Set Arc always produces exactly 50 tracks in 1 playlist
        system_text = DJ_SET_ARC_SYSTEM
    else:
        raise ValueError(f"Unknown multi-playlist recipe: {recipe}")

    user_prompt = (
        f"Available Catalog ({len(catalog)} tracks):\n"
        f"{json.dumps(catalog, ensure_ascii=False)}"
    )

    logger.info(
        "gemini_multi_curate_started",
        model=MODEL_ID,
        recipe=recipe.value,
        catalog_size=len(catalog),
        per_playlist_limit=track_count,
    )

    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=user_prompt,
            config=genai.types.GenerateContentConfig(
                system_instruction=system_text,
                response_mime_type="application/json",
                response_schema=GeminiMultiPlaylistResult,
            ),
        )

        result = response.parsed
        if result is None:
            raise RuntimeError(
                f"Gemini returned unparseable response: {response.text}"
            )

        ai_usage = _calculate_usage(response)

        total_tracks = sum(len(p.curated_video_ids) for p in result.playlists)
        logger.info(
            "gemini_multi_curate_success",
            recipe=recipe.value,
            playlist_count=len(result.playlists),
            total_tracks=total_tracks,
            **ai_usage,
        )
        return result, ai_usage

    except Exception as exc:
        logger.error("gemini_multi_curate_failed", recipe=recipe.value, error=str(exc))
        raise RuntimeError(f"Gemini multi-playlist curation failed: {exc}") from exc
