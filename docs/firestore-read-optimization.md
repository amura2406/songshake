# Firestore Read Optimization

This document captures the investigation and fixes applied to reduce excessive Firestore read operations in the SongShake application.

## Problem

With a single user and ~962 tracks, the application was consuming **363K Firestore reads per hour** — well beyond free-tier limits. Root cause: every "fetch tracks" call reads all documents twice (962 `track_owners` + 962 `tracks`), and multiple frontend components were polling independently.

## Root Cause Analysis

Each call to `get_all_tracks()` performs:
1. **962 reads** — `track_owners WHERE owner == ?` (all ownership docs)
2. **962 reads** — `tracks WHERE videoId IN [batch]` (32 batches × ~30 docs)

**Total: ~1,924 reads per fetch.**

### Read Sources (before fix)

| Source | Interval | Reads/Call | Reads/Hour |
|--------|----------|-----------|------------|
| Layout sidebar `getTags()` poll | 60s + every route change | ~1,924 | ~115K |
| Results `getSongsWithTags()` double-fire | Every page nav | ~1,924 | ~50K |
| Dashboard `getPlaylists()` poll | 30s | ~28 | ~3.4K |
| `useJobs` `getJobs()` poll | 10s | ~16 | ~5.8K |
| `useAIUsage` `getAIUsage()` poll | 2s | 1 | ~1.8K |

## Fixes Applied

### 1. Removed Layout Tag Polling (~115K reads/hr saved)

**Before:** Layout fetched tags every 60s via `setInterval` AND re-fetched on every `location.pathname` change (every navigation).

**After:** Tags load once on mount. The sidebar tag counts are stable enough for a single session.

### 2. Backend TTL Cache on `get_all_tracks()` (~80% of remaining reads)

Added a per-owner, 60-second in-memory TTL cache. Back-to-back API calls within 60s hit the cache instead of Firestore. Cache is automatically invalidated on:
- `save_track()` — new/updated tracks
- `delete_tracks()` — bulk deletion
- `wipe_db()` — database reset

### 3. Deduplicated Frontend Fetch (~50K reads/hr saved)

Added a `useRef` loading guard in `Results.jsx` to prevent concurrent `getSongsWithTags()` calls caused by React state cascades (`setPage(0)` triggering a re-render that refires the data-fetching effect).

### 4. Demand-Only Polling (~8K reads/hr saved)

- **AI Usage:** No polling by default. 2s polling starts only when enrichment jobs are active, stops when they finish.
- **Jobs:** Polls only when active jobs exist. Stops when all jobs complete.
- **Dashboard:** No periodic polling. Fetches playlists on mount only.

## Expected Impact

| Metric | Before | After |
|--------|--------|-------|
| Reads/hour (idle) | ~363K | <10K |
| Reads per page load | ~3,848 (double-fire) | ~1,924 (single, often cached) |
| Polling overhead | ~176K reads/hr | ~0 reads/hr (idle) |

## Key Takeaway

> **Every Firestore `.where()` query counts as 1 read per document returned.** With ~962 tracks, a single `get_all_tracks()` call costs ~1,924 reads. Multiply by polling intervals and redundant calls, and costs escalate quickly for even a single user.

Mitigations:
- **Cache aggressively** — tracks change infrequently (only during enrichment/deletion)
- **Never poll for static data** — use on-demand fetching
- **Deduplicate frontend calls** — React effects can fire multiple times
- **Monitor Firestore usage** — Firebase Console → Usage tab → "Top queries by load"
