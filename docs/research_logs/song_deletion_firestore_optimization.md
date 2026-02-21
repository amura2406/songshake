# Research Log: Song Deletion & Firestore Optimization

## Date: 2026-02-21

## Firestore Collection Map

| Collection | Adapter | Purpose | Read Hotspots |
|---|---|---|---|
| `tracks` | `FirestoreSongsAdapter` | Global song catalog (de-duped by videoId) | `get_all_tracks()`, `get_tags()`, `get_failed_tracks()` |
| `track_owners` | `FirestoreSongsAdapter` | Ownership links (`{owner}_{videoId}`) | `get_all_tracks()` (query first) |
| `enrichment_history` | `FirestoreSongsAdapter` | Playlist processing history | `get_enrichment_history()` |
| `task_states` | `FirestoreSongsAdapter` | Background task state | Point reads only |
| `jobs` | `FirestoreJobsAdapter` | Job queue/history | Multiple queries + transactions |
| `ai_usage` | `FirestoreJobsAdapter` | Token usage counters | Point reads + increments |
| `google_tokens` | `FirestoreTokenAdapter` | OAuth tokens per user | Point reads only |
| `vibe_playlists` | `FirestoreVibingAdapter` | AI DJ playlist CRUD | Point reads + owner queries |
| `youtube_quota` | `FirestoreVibingAdapter` | YouTube API quota tracking | Point reads + increments |

## Read Pattern Analysis

### Current Flow: Page Load on /results (Database view)

```
Frontend:
  1. getSongs()  → GET /api/songs
  2. getTags()   → GET /api/tags     (called in parallel)

Backend (for each call):
  GET /api/songs:
    → storage.get_all_tracks(owner)
      → Read track_owners WHERE owner == X           [READ: N docs]
      → Read tracks WHERE videoId IN [batch of 30]   [READ: M docs]
    → Filter in Python (tags, BPM, pagination)
    → Return paginated items

  GET /api/tags:
    → storage.get_tags(owner)
      → self.get_all_tracks(owner)                   [DUPLICATE!]
        → Read track_owners WHERE owner == X         [READ: N docs again]
        → Read tracks WHERE videoId IN [batch]       [READ: M docs again]
      → Compute tag counts from tracks
      → Return tags
```

**Total reads per page load: ~2N + 2⌈M/30⌉ queries**

For 700 songs: ~46 read round-trips per page load × 2 endpoints = ~92 read operations.

### Optimization: Combined Endpoint

One call, one pass through `get_all_tracks()`:
- Read `track_owners` once → N docs
- Read `tracks` in batches → ⌈M/30⌉ queries
- Compute tags from same data (pure function, no Firestore reads)
- Return `{items, total, page, pages, tags}`

**Savings: ~50% reduction in Firestore reads per page load.**

## Deletion Design

### Data Model
- `tracks/{videoId}` — shared global catalog, can be owned by multiple users
- `track_owners/{owner}_{videoId}` — ownership link, one per (owner, track) pair

### Delete Strategy
1. Always delete `track_owners/{owner}_{videoId}` for each selected track
2. For `tracks/{videoId}`: check if other owners reference it. If orphaned, delete it
3. Use Firestore batched writes (max 500 per batch) for efficiency
4. Return count of deleted ownership links

### Existing Test Patterns
- Unit tests: `MagicMock` on `StoragePort`, FastAPI `TestClient`, dependency override
- Integration tests: Real Firestore via `conftest.py` fixtures, `wipe_db()` cleanup
