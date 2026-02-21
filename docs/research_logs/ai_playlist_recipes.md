# AI Playlist Recipes — Research Log

## Date: 2026-02-21

## Context

Adding 4 new AI playlist recipes to the existing "Playlist Vibing" feature. Currently, the feature uses a single strategy: pick the most neglected track as seed → Gemini curates N tracks around it.

## Existing Architecture

### Data Model (per track in Firestore)
- `videoId`, `title`, `artists`, `album`, `year`
- `genres: list[str]` — from taxonomy (75+ options)
- `moods: list[str]` — from taxonomy (48 options)
- `instruments: list[str]` — from taxonomy (50+ options)
- `bpm: int | None`
- `vocalType: "Vocals" | "Instrumental" | None`
- `thumbnails`, `playCount`, `isMusic`, `status`

### Current Vibing Flow
1. `VibeRequest(track_count)` → `POST /vibing/generate`
2. Fetch all tracks for owner → `select_seed_track()` picks most neglected
3. `minify_catalog()` strips to: `videoId, title, artist_names, genres, moods, bpm`
4. `curate_playlist()` calls Gemini with seed + catalog → `GeminiCurationResult`
5. Save as `vibe_playlist` doc (status: "draft")
6. User can view, preview, then "Approve & Sync" to YouTube

### Key Observation: `minify_catalog` does NOT include `instruments` or `vocalType`
These fields are needed for Recipes 2 and 3. Must be added.

## New Recipes

### Recipe 1: "Energy Zones" (BPM + Moods)
- Pre-sort catalog by BPM before sending to Gemini
- Gemini produces 3 playlists with BPM/mood constraints
- Vol 1 (< 110 BPM, Atmospheric/Melancholic/Relaxed)
- Vol 2 (110-124 BPM, Groovy/Danceable)  
- Vol 3 (> 125 BPM, Energetic/Intense/Euphoric)
- No track overlap between playlists

### Recipe 2: "Aesthetic Universes" (Genre + Instrument Clustering)
- Gemini clusters by overlapping genres and instruments
- Dynamic number of playlists (3-12 depending on library diversity)
- No track overlap

### Recipe 3: "Vocal Divide" (Vocal vs Instrumental)
- Split by vocal presence (uses `vocalType` and `instruments`)
- Gemini also considers mood/BPM cohesion within each playlist
- 2 playlists

### Recipe 4: "DJ Set Arc" (Narrative Storytelling)
- Always exactly 50 tracks
- Warm-up → Peak → Climax → Cool-down narrative arc
- Tracks ordered for BPM progression

## Design Decisions

### Multi-playlist storage: Flat with `batch_id`
Each recipe that generates multiple playlists creates N separate `vibe_playlist` documents, all sharing the same `batch_id` and `recipe` field. This reuses existing approve/sync/delete flows without requiring a new collection or parent document structure.

### Gemini response schema per recipe type
- "Neglected Gems" → `GeminiCurationResult` (unchanged)
- All other recipes → `GeminiMultiPlaylistResult` with `playlists: list[{title, description, curated_video_ids}]`

### Track count behavior
- Per-playlist limit for multi-recipes is `track_count / num_playlists` (approximately)
- DJ Set Arc: always 50 tracks, ignores track_count
