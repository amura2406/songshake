# Research Log: Job System for Song Enrichment

## Current Architecture

### Backend
- **Framework:** FastAPI (Python) with TinyDB as embedded JSON database
- **Enrichment flow:** `process_playlist()` in `enrichment.py` with DI ports (StoragePort, PlaylistFetcher, AudioDownloader, AudioEnricher)
- **Streaming:** SSE via `StreamingResponse` in `routes.py`, polls in-memory dict every 0.5s
- **Task state:** In-memory `enrichment_tasks` dict, persisted to TinyDB on completion/error via `storage.save_task_state()`
- **Task ID format:** `{playlist_id}_{random_hex}` — used to derive playlist_id in `routes_playlists.py`

### Frontend
- **Framework:** React 19 + React Router v7 + TailwindCSS v4 + Framer Motion
- **Current flow:** Dashboard → click "Identify Songs" → `navigate(/enrichment/{taskId})` → dedicated Enrichment page with SSE progress bar
- **Layout:** Sidebar (moods/genres/stats) + top navbar (logo, profile dropdown)
- **API client:** Axios with `/api` proxy to backend port 8000

## Key Patterns Observed

| Pattern | Location | Notes |
|---------|----------|-------|
| DI ports/protocols | `platform/protocols.py` | typing.Protocol classes for I/O abstraction |
| Structured logging | `platform/logging_config.py` | `get_logger()` with structured fields |
| TinyDB tables | `songs/storage.py` | Separate tables: songs, user_songs, history, tasks |
| In-memory + persist | `enrichment/routes.py` | Fast SSE reads from dict, persist on complete |
| SSE streaming | `enrichment/routes.py` | `StreamingResponse` with `text/event-stream` |

## Technologies Researched

### Streamable HTTP (SSE for AI Usage)
Using the same SSE pattern already in the codebase. For AI usage, a separate SSE endpoint will broadcast
token/cost updates as enrichment progresses. The frontend will use `EventSource` to listen.

> I am relying on my training data for SSE patterns as external verification was unavailable.

### Job Cancellation
Python `threading.Event` will be used as a cancellation signal. The enrichment loop checks
`cancel_event.is_set()` before each track. The event is stored in-memory alongside the job.

> I am relying on my training data for threading.Event patterns.

### Framer Motion Animations
Already in the project's dependencies. Will use `motion.div` with `animate`, `whileHover`, and
`AnimatePresence` for job modal, pulse animations on active playlists, and glow effects on
AI usage text updates.

## Architecture Decision
No ADR needed — this extends existing patterns (SSE streaming, TinyDB storage, in-memory state)
rather than introducing fundamentally new architectural choices.
