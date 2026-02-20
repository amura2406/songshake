"""Production AudioEnricher adapter wrapping Gemini genai.Client.

Uses URL-based enrichment: passes YouTube URL to Gemini with google_search
tool for musical analysis. No audio download needed.
"""

import json

from google import genai
from google.genai import types

from song_shake.features.enrichment.enrichment import TokenTracker
from song_shake.features.enrichment.taxonomy import (
    genres_prompt_list,
    instruments_prompt_list,
    moods_prompt_list,
)
from song_shake.platform.logging_config import get_logger

logger = get_logger(__name__)

_URL_PROMPT_TEMPLATE = """Analyze this YouTube Music track and provide musical metadata.

YouTube URL: https://music.youtube.com/watch?v={video_id}
Title: {title}
Artist: {artist}

Return a JSON object with:

1. "genres": list of 1-4 genres. Pick ONLY from this standardized list (choose the most specific applicable):
   {genres}

2. "moods": list of 2-4 moods. Pick ONLY from this standardized list:
   {moods}

3. "bpm": integer (beats per minute)

4. "instruments": list of 1-5 main instruments heard in the track. Pick ONLY from this standardized list:
   {instruments}

5. "vocal_type": one of "Vocals" or "Instrumental"
   - "Vocals" if the track has singing, rapping, or prominent vocal performance
   - "Instrumental" if the track has no vocals or only minor vocal samples

6. "album": object with the album this track belongs to:
   - "name": the album title (e.g. "Nocturnal")
   - "year": the release year as a string (e.g. "2022")
   If you cannot determine the album, set "album" to null.

Return ONLY the JSON object."""


class GeminiEnricherAdapter:
    """Wraps genai.Client behind AudioEnricher protocol.

    Uses URL-based enrichment — no audio download or file upload needed.
    After calling enrich_by_url(), the returned dict includes 'usage_metadata'
    so callers can update their own TokenTracker without coupling to genai.
    """

    def __init__(self, api_key: str):
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=120_000),
        )

    def enrich_by_url(self, video_id: str, title: str, artist: str) -> dict:
        """Enrich a track via YouTube URL — no audio download needed.

        Uses Gemini 3 Flash Preview with the google_search tool to analyze
        the YouTube Music URL directly.

        Returns dict with genres, moods, instruments, bpm, vocal_type, album,
        and 'usage_metadata': {'prompt_tokens': int, 'candidates_tokens': int}.
        """
        prompt = _URL_PROMPT_TEMPLATE.format(
            video_id=video_id,
            title=title,
            artist=artist,
            genres=genres_prompt_list(),
            moods=moods_prompt_list(),
            instruments=instruments_prompt_list(),
        )

        logger.info(
            "gemini_url_enrich_started",
            video_id=video_id,
            title=title,
            artist=artist,
        )

        response = self._client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                tools=[types.Tool(google_search=types.GoogleSearch())],
            ),
        )

        usage = response.usage_metadata
        prompt_tokens = usage.prompt_token_count if usage else 0
        candidates_tokens = usage.candidates_token_count if usage else 0

        logger.info(
            "gemini_url_enrich_completed",
            video_id=video_id,
            prompt_tokens=prompt_tokens,
            candidates_tokens=candidates_tokens,
        )

        result = json.loads(response.text)
        result["usage_metadata"] = {
            "prompt_tokens": prompt_tokens,
            "candidates_tokens": candidates_tokens,
        }
        return result
