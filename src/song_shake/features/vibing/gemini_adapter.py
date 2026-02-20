"""Gemini AI DJ adapter — curates playlists via google-genai SDK."""

import json
import os

from google import genai

from song_shake.features.vibing.logic import extract_artist_string, minify_catalog
from song_shake.features.vibing.models import GeminiCurationResult
from song_shake.platform.logging_config import get_logger

logger = get_logger(__name__)

SYSTEM_INSTRUCTION = (
    "You are an expert DJ and music curator. I am providing a 'Seed Track' and "
    "a JSON catalog of available tracks. Select exactly {track_count} tracks "
    "from the catalog that create the most musically cohesive and aesthetically "
    "pleasing playlist around the Seed Track. Pay attention to BPM flow, genre "
    "blending, and mood progression. Return ONLY videoIds that exist in the "
    "provided catalog. Also provide a short 1-2 sentence description explaining "
    "the playlist's vibe: what musical thread ties these tracks together, and "
    "what journey the listener will experience."
)

MODEL_ID = "gemini-3.1-pro-preview"

# Gemini 3.1 Pro Preview pricing (USD per 1M tokens)
PRICE_INPUT_PER_1M = 1.25
PRICE_OUTPUT_PER_1M = 10.00


def curate_playlist(
    seed_track: dict,
    remaining_tracks: list[dict],
    track_count: int = 49,
) -> tuple[GeminiCurationResult, dict]:
    """Call Gemini to curate a playlist around the seed track.

    Args:
        seed_track: The seed track dict (full data).
        remaining_tracks: The remaining catalog (full data).
        track_count: Number of tracks to curate (excluding seed).

    Returns:
        A tuple of (GeminiCurationResult, ai_usage_dict).
        ai_usage_dict has keys: input_tokens, output_tokens, cost.

    Raises:
        RuntimeError: If Gemini call fails or returns unparseable data.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY environment variable is not set.")

    client = genai.Client(api_key=api_key)

    # Minify the catalog for token efficiency
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

    system_text = SYSTEM_INSTRUCTION.format(track_count=track_count)

    logger.info(
        "gemini_curate_started",
        model=MODEL_ID,
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

        # Extract token usage from response metadata
        input_tokens = 0
        output_tokens = 0
        if response.usage_metadata:
            input_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
            output_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0

        cost = (
            (input_tokens / 1_000_000) * PRICE_INPUT_PER_1M
            + (output_tokens / 1_000_000) * PRICE_OUTPUT_PER_1M
        )

        ai_usage = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": round(cost, 6),
        }

        logger.info(
            "gemini_curate_success",
            playlist_title=result.generated_playlist_title,
            curated_count=len(result.curated_video_ids),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=ai_usage["cost"],
        )
        return result, ai_usage

    except Exception as exc:
        logger.error("gemini_curate_failed", error=str(exc))
        raise RuntimeError(f"Gemini curation failed: {exc}") from exc
