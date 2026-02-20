"""CLI script to test Gemini AI DJ curation with real track data.

Reads tracks.json, selects a seed, sends to Gemini, prints results.
Run: .venv/bin/python src/song_shake/features/vibing/test_gemini_live.py
"""

import json
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from dotenv import load_dotenv

load_dotenv()

from song_shake.features.vibing.logic import (
    build_final_playlist,
    extract_artist_string,
    minify_catalog,
    select_seed_track,
)
from song_shake.features.vibing.gemini_adapter import curate_playlist


def main():
    tracks_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "tracks.json")
    tracks_path = os.path.abspath(tracks_path)

    print(f"Loading tracks from: {tracks_path}")
    with open(tracks_path) as f:
        all_tracks = json.load(f)

    # Filter to isMusic == True only
    music_tracks = [t for t in all_tracks if t.get("isMusic") is True]
    print(f"Total tracks: {len(all_tracks)}, Music tracks: {len(music_tracks)}")

    # Phase 1: Seed selection (no last_playlisted_at in local data → first by sort)
    seed, remaining = select_seed_track(music_tracks)
    print(f"\n🌱 Seed Track: \"{seed.get('title')}\" by {extract_artist_string(seed)}")
    print(f"   Genres: {seed.get('genres', [])}")
    print(f"   Moods: {seed.get('moods', [])}")
    print(f"   BPM: {seed.get('bpm')}")
    print(f"\n📀 Catalog size: {len(remaining)} tracks")

    # Phase 2: Gemini curation
    print("\n🎧 Calling Gemini (gemini-3.1-pro-preview) for AI DJ curation...")
    print("   Requesting 49 tracks...")

    try:
        result = curate_playlist(seed, remaining, track_count=49)
    except RuntimeError as e:
        print(f"\n❌ Gemini call failed: {e}")
        sys.exit(1)

    print(f"\n✅ Gemini returned successfully!")
    print(f"   Playlist Title: \"{result.generated_playlist_title}\"")
    print(f"   Curated track count: {len(result.curated_video_ids)}")

    # Build final playlist
    final_ids = build_final_playlist(seed["videoId"], result.curated_video_ids)
    print(f"\n🎵 Final playlist: {len(final_ids)} tracks")

    # Print the playlist with track details
    track_map = {t["videoId"]: t for t in music_tracks}
    print(f"\n{'#':>3}  {'Title':<50}  {'Artist':<30}  {'BPM':>4}  {'Genres'}")
    print("-" * 130)
    for i, vid in enumerate(final_ids[:50]):
        t = track_map.get(vid)
        if t:
            title = t.get("title", "?")[:48]
            artist = extract_artist_string(t)[:28]
            bpm = str(t.get("bpm", "?"))
            genres = ", ".join(t.get("genres", [])[:3])
            marker = " 🌱" if vid == seed["videoId"] else ""
            print(f"{i+1:>3}  {title:<50}  {artist:<30}  {bpm:>4}  {genres}{marker}")
        else:
            print(f"{i+1:>3}  (unknown videoId: {vid})")

    # Verify all curated IDs exist in catalog
    catalog_ids = {t["videoId"] for t in remaining}
    invalid = [vid for vid in result.curated_video_ids if vid not in catalog_ids]
    if invalid:
        print(f"\n⚠️  {len(invalid)} curated IDs NOT in catalog: {invalid[:5]}")
    else:
        print(f"\n✅ All curated IDs are valid catalog tracks!")


if __name__ == "__main__":
    main()
