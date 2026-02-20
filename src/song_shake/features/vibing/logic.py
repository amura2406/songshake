"""Pure business logic for Playlist Vibing.

All functions are pure (no I/O, no side-effects) so they can be
unit-tested without infrastructure.
"""

from datetime import datetime, timezone


def select_seed_track(
    tracks: list[dict],
) -> tuple[dict, list[dict]]:
    """Pick the most "neglected" track as the seed.

    The seed is the track with the oldest ``last_playlisted_at``.
    Tracks where the field is missing or ``None`` are treated as the
    absolute oldest and prioritised first.

    Returns:
        (seed_track, remaining_catalog)

    Raises:
        ValueError: If *tracks* is empty.
    """
    if not tracks:
        raise ValueError("Cannot select a seed from an empty track list.")

    # Sort: None → epoch-zero (oldest possible), then by timestamp ascending
    epoch_zero = datetime(1970, 1, 1, tzinfo=timezone.utc)

    def _sort_key(t: dict) -> datetime:
        ts = t.get("last_playlisted_at")
        if ts is None:
            return epoch_zero
        if isinstance(ts, datetime):
            return ts
        # Firestore may return a DatetimeWithNanoseconds or string
        try:
            return datetime.fromisoformat(str(ts))
        except (ValueError, TypeError):
            return epoch_zero

    sorted_tracks = sorted(tracks, key=_sort_key)
    seed = sorted_tracks[0]
    remaining = sorted_tracks[1:]
    return seed, remaining


def minify_catalog(tracks: list[dict]) -> list[dict]:
    """Strip heavy fields to save Gemini token context.

    Returns a list of lightweight dicts with only the fields needed
    for AI curation.
    """
    minified = []
    for t in tracks:
        artists_raw = t.get("artists", [])
        if isinstance(artists_raw, list):
            artist_names = [
                a["name"] if isinstance(a, dict) else str(a) for a in artists_raw
            ]
        else:
            artist_names = [str(artists_raw)]

        minified.append(
            {
                "videoId": t["videoId"],
                "title": t.get("title", ""),
                "artist_names": artist_names,
                "genres": t.get("genres", []),
                "moods": t.get("moods", []),
                "bpm": t.get("bpm"),
            }
        )
    return minified


def build_final_playlist(seed_id: str, curated_ids: list[str]) -> list[str]:
    """Combine seed + curated IDs, ensuring no duplicates.

    The seed is always first.
    """
    seen: set[str] = {seed_id}
    result = [seed_id]
    for vid in curated_ids:
        if vid not in seen:
            seen.add(vid)
            result.append(vid)
    return result


def extract_artist_string(track: dict) -> str:
    """Extract a comma-separated artist string from a track dict."""
    artists_raw = track.get("artists", [])
    if isinstance(artists_raw, list):
        names = [
            a["name"] if isinstance(a, dict) else str(a) for a in artists_raw
        ]
        return ", ".join(names) if names else "Unknown"
    return str(artists_raw) if artists_raw else "Unknown"
