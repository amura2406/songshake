"""Production AudioEnricher adapter wrapping Gemini genai.Client."""

from google import genai

from song_shake.features.enrichment.enrichment import enrich_track, TokenTracker


class GeminiEnricherAdapter:
    """Wraps genai.Client + enrich_track() behind AudioEnricher.

    The adapter owns the Gemini client and an internal TokenTracker.
    After calling enrich(), the returned dict includes 'usage_metadata'
    so callers can update their own TokenTracker without coupling to genai.
    """

    def __init__(self, api_key: str):
        self._client = genai.Client(api_key=api_key)
        # Internal tracker used by enrich_track to accumulate usage info
        self._tracker = TokenTracker()

    def enrich(self, file_path: str, title: str, artist: str) -> dict:
        """Enrich a track with AI-generated metadata.

        Returns dict with genres, moods, instruments, bpm, and
        'usage_metadata': {'prompt_tokens': int, 'candidates_tokens': int}.
        """
        # Snapshot before
        prev_input = self._tracker.input_tokens
        prev_output = self._tracker.output_tokens

        result = enrich_track(self._client, file_path, title, artist, self._tracker)

        # Attach delta usage so caller can track independently
        result["usage_metadata"] = {
            "prompt_tokens": self._tracker.input_tokens - prev_input,
            "candidates_tokens": self._tracker.output_tokens - prev_output,
        }
        return result
