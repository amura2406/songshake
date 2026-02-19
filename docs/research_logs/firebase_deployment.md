# Research Log: Firebase Deployment

## Date: 2026-02-18

## Objective
Research deploying Song Shake to Firebase with free tier constraints, storage abstraction toggle, IaC, and security.

---

## Current Architecture Analysis

### Backend (Python/FastAPI)
- **Entry point**: `src/song_shake/api.py` — FastAPI app with CORS middleware
- **Features**: auth, enrichment, explore, jobs, songs (5 feature slices)
- **Storage**: TinyDB (`songs.db`) — local JSON file database
  - Tables: `songs`, `user_songs`, `history`, `tasks`, `jobs`, `ai_usage`
  - Thread-safe with `threading.Lock()` per module
- **Auth**: Google OAuth via `oauth.json` file + `ytmusicapi`
- **Enrichment**: Gemini 3 Flash + yt-dlp (audio download) + ffmpeg (audio conversion)
- **Dependencies requiring server-side runtime**: `yt-dlp`, `ffmpeg`, `google-genai`

### Frontend (React/Vite)
- React 19 + Tailwind CSS 4 + Framer Motion
- Vite dev server proxies `/api` → `http://127.0.0.1:8000`
- Axios-based API layer (`web/src/api.js`)

### Existing I/O Abstractions
- `platform/protocols.py` defines `StoragePort`, `AudioDownloader`, `AudioEnricher`, `PlaylistFetcher`
- `enrichment/storage_adapter.py` implements `TinyDBStorageAdapter` wrapping songs/storage
- **Gap**: Songs routes and Jobs routes call storage modules directly (no port abstraction)

---

## Firebase Services Research

### Firebase Free Tier (Spark Plan) — Sufficient for Few Users

| Service | Free Tier Limit | Song Shake Needs | Verdict |
|---------|----------------|-------------------|---------|
| **Cloud Run** | 180K vCPU-sec/mo, 360K GiB-sec/mo, 2M req/mo | Low req volume, occasional enrichments | ✅ Plenty |
| **Firestore** | 50K reads/day, 20K writes/day, 1 GiB storage | ~few hundred tracks per user | ✅ Plenty |
| **Hosting** | 1 GB storage, 10 GB transfer/mo | React SPA ~5 MB, low traffic | ✅ Plenty |
| **Cloud Build** | 120 build-min/day | Occasional deploys | ✅ Plenty |

### Key Constraint
- Cloud Run free tier only in `us-central1`, `us-east1`, `us-west1`
- Firestore free tier: only 1 database per project

### Architecture Decision: Cloud Run over Cloud Functions
- **Cloud Run chosen** because:
  - yt-dlp + ffmpeg need a custom Docker image (can't run in Cloud Functions)
  - FastAPI is a full WSGI/ASGI server, not individual functions
  - Cloud Run supports long-running requests (enrichment can take minutes)
  - Cloud Run scales to zero (no cost when idle)

---

## Storage Toggle Mechanism

### Approach: Environment-Based Storage Backend Selection

The project already has `StoragePort` Protocol. The plan is to:

1. **Create `FirestoreStorageAdapter`** implementing `StoragePort`
2. **Create a storage factory** that reads `STORAGE_BACKEND` env var
3. **Refactor routes** to use dependency injection instead of direct import

Toggle mechanism:
```python
# ENV: STORAGE_BACKEND=tinydb (default for local) or STORAGE_BACKEND=firestore (for cloud)
```

### Firestore Collection Design (mapping from TinyDB tables)

| TinyDB Table | Firestore Collection | Key |
|-------------|---------------------|-----|
| `songs` | `songs` | `videoId` |
| `user_songs` | `users/{owner}/songs` | `videoId` |
| `history` | `users/{owner}/history` | `playlistId` |
| `jobs` | `jobs` | `id` |
| `ai_usage` | `users/{owner}/ai_usage` | (single doc) |
| `tasks` | `tasks` | `task_id` |

---

## Deployment Strategy

### Firebase Hosting + Cloud Run Architecture
```
┌─────────────────────────┐
│   Firebase Hosting      │
│   (React SPA - CDN)     │
│                         │
│   /api/* → Cloud Run    │
│   /auth/* → Cloud Run   │
│   /* → index.html       │
└──────────┬──────────────┘
           │ rewrite
┌──────────▼──────────────┐
│   Cloud Run             │
│   (FastAPI + Docker)    │
│   yt-dlp, ffmpeg        │
│                         │
│   → Firestore           │
│   → Gemini AI           │
│   → YouTube APIs        │
└─────────────────────────┘
```

### IaC: Firebase CLI + `firebase.json`
- `firebase.json` defines hosting config, rewrites, deploy targets
- `Dockerfile` for Cloud Run container
- Single `firebase deploy` command deploys everything

### Security Considerations
- **CORS**: Lock down to Firebase Hosting domain only
- **Auth on Cloud**: Move from file-based `oauth.json` to Firestore-stored tokens
- **Secrets**: Use Cloud Run environment variables / Secret Manager for API keys
- **Firestore Rules**: Lock down to authenticated users only
- **HTTPS**: Automatic via Firebase Hosting

---

## Cloud Run Background Task Behavior

### Problem
Song Shake's enrichment feature uses FastAPI `BackgroundTasks` for long-running jobs. Default Cloud Run **throttles CPU after HTTP response**, killing background tasks.

### Research Findings
- Default Cloud Run is "request-scoped" — CPU is allocated only while processing a request
- After response is sent, CPU is severely throttled or disabled
- FastAPI `BackgroundTasks` execute in the same process after the response — they get killed
- Instances remain idle for ~15 min before shutdown (if no `min-instances`)

### Options Evaluated
1. **`--no-cpu-throttling` (CPU always allocated)** — CPU stays on between requests; billing changes to instance-based but still within free tier for low usage. Instance still scales to zero when idle.
2. **SSE streaming** — existing pattern keeps HTTP connection alive = CPU stays allocated. But if user closes browser, job dies.
3. **Cloud Run Jobs** — purpose-built for batch workloads. Requires significant restructuring (separate trigger mechanism).
4. **Cloud Tasks** — most robust with retries. Over-engineered for few users.

### Decision
Use `--no-cpu-throttling` + existing SSE streaming (defense in depth). Free tier impact: A 15-minute enrichment ≈ 900 vCPU-sec. Need ~200 sessions/month to exceed 180K free vCPU-sec.

---

## No Docker Locally — Cloud Build Alternative

### Problem
Developer machine doesn't have Docker and can't install it.

### Solution: `gcloud run deploy --source .`
- Zips source + Dockerfile, uploads to Cloud Build
- Cloud Build builds the Docker image remotely
- Pushes image to Artifact Registry
- Deploys to Cloud Run
- **No local Docker daemon needed at all**
- Cloud Build free tier: 120 build-min/day (~3-5 min per deploy)
- Dockerfile is authored as a text file in the repo but built in the cloud

### Key Requirement
- Still need a `Dockerfile` in the repo for Cloud Build to use
- Buildpacks (alternative to Dockerfile) don't include system packages like ffmpeg
- Therefore Dockerfile is required for `apt-get install ffmpeg`
- `gcloud` CLI is the only local prerequisite

---

## Gotchas & Edge Cases

1. **yt-dlp in Cloud Run**: Works fine in Docker containers. Need `ffmpeg` in the image.
2. **Background tasks**: FastAPI `BackgroundTasks` work in Cloud Run but container may shut down. Need to handle gracefully with timeout settings.
3. **oauth.json on Cloud**: Cannot use file-based auth. Must store in Firestore or use server-side session.
4. **Cold starts**: Cloud Run scales to zero. First request after idle will be slow (~5-10s). Acceptable for few users.
5. **Cloud Run timeout**: Default 5 min, max 60 min. Enrichment of large playlists may need extended timeout.
6. **Explore feature**: Dev-only tool — should be disabled in production for security.
