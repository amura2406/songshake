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
    for AI curation, including instruments and vocalType for
    multi-recipe support.
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

        entry: dict = {
            "videoId": t["videoId"],
            "title": t.get("title", ""),
            "artist_names": artist_names,
            "genres": t.get("genres", []),
            "moods": t.get("moods", []),
            "bpm": t.get("bpm"),
            "instruments": t.get("instruments", []),
            "vocalType": t.get("vocalType"),
        }
        minified.append(entry)
    return minified


def pre_sort_by_bpm(tracks: list[dict]) -> list[dict]:
    """Sort minified catalog by BPM ascending.

    Tracks with ``None`` or missing BPM are placed at the end.
    """

    def _bpm_key(t: dict) -> tuple[int, int]:
        bpm = t.get("bpm")
        if bpm is None:
            return (1, 0)  # None → sort last
        return (0, int(bpm))

    return sorted(tracks, key=_bpm_key)


def validate_no_cross_playlist_duplicates(
    playlists: list[dict],
    track_limit: int,
) -> list[dict]:
    """Validate and enforce cross-playlist constraints.

    - No track appears in more than one playlist.
    - Each playlist respects ``track_limit`` (if > 0).

    Duplicates in later playlists are silently removed.

    Returns:
        The cleaned playlists (same structure, deduplicated).
    """
    seen_globally: set[str] = set()
    cleaned = []

    for pl in playlists:
        deduped_ids = []
        for vid in pl.get("curated_video_ids", []):
            if vid not in seen_globally:
                seen_globally.add(vid)
                deduped_ids.append(vid)
                if 0 < track_limit <= len(deduped_ids):
                    break

        cleaned.append({
            **pl,
            "curated_video_ids": deduped_ids,
        })

    return cleaned


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
