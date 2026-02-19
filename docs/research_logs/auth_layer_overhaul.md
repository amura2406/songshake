# Research Log: Auth Layer Overhaul

## Date: 2026-02-19

## Context
SongShake uses Google OAuth to authenticate users and access YouTube Data API v3 for playlist data. The current auth implementation has critical architectural issues that prevent multi-user support and leave all API endpoints unprotected.

## Current Architecture Analysis

### Backend Auth (`src/song_shake/features/auth/`)

#### `auth.py` — Core Auth Module
- `get_ytmusic()` reads `oauth.json` from disk, builds `YTMusic` client with OAuth credentials
- `ensure_fresh_access_token()` reads/refreshes Google tokens from `oauth.json` flat file
- `get_data_api_playlists()` / `get_data_api_tracks()` use the Google access token for YouTube Data API v3
- `setup_auth()` — CLI-only, pastes raw headers (legacy browser auth flow)
- **All functions operate on a single global `oauth.json` file**

#### `routes.py` — Auth HTTP Endpoints
| Route | Purpose | Issue |
|-------|---------|-------|
| `GET /auth/google/login` | Redirects to Google OAuth consent | ✅ OK |
| `GET /auth/google/callback` | Exchanges code → tokens, writes `oauth.json`, redirects to frontend | ⚠️ Overwrites single file |
| `GET /auth/status` | Reads `oauth.json`, checks `expires_at` | ⚠️ Single-user, no JWT |
| `GET /auth/me` | Reads `oauth.json` token, calls Google APIs for user profile | ⚠️ No session concept |
| `GET /auth/refresh` | Refreshes Google token in `oauth.json` | ⚠️ Single-user |
| `GET /auth/logout` | Deletes `oauth.json` | ⚠️ Logs out ALL users |

### Key Problems Identified

#### P1: Single-User Token Storage (CRITICAL)
- `oauth.json` is a single flat file at project root
- When User B logs in, User A's tokens are overwritten
- `logout` deletes the file entirely, affecting everyone

#### P2: No App-Level Session / JWT (CRITICAL)
- The app has no concept of "sessions" or its own tokens
- Frontend checks auth by calling `/auth/status` which reads the flat file
- No way to identify which user is making a request
- The Google OAuth token IS the session — these should be separate concepts

#### P3: No Backend Route Protection (CRITICAL)
- Only `routes_playlists.py` uses `Depends(get_ytmusic)` which is an auth-adjacent check (reads `oauth.json`)
- `routes.py` (songs) — NO auth, accepts `owner` as a query param (anyone can read anyone's songs)
- `routes.py` (jobs) — NO auth at all
- All API endpoints are fully accessible without authentication

#### P4: Owner Identity is Faked
- Hardcoded `owner='web_user'` throughout songs and jobs routes
- Frontend passes `owner` as a parameter — trivially spoofable
- No correlation between authenticated user and data ownership

#### P5: Google Token vs App Token Conflation
- The Google OAuth access_token is used directly as the "session"
- `/auth/status` checks if the Google token is expired — this is checking Google's auth, not the app's
- Token refresh logic refreshes the Google token, not an app session

### Frontend Auth (`web/src/`)

#### `App.jsx`
- `PrivateRoute` component wraps protected routes
- Calls `checkAuth()` on mount → hits `/auth/status`
- Redirects to `/login` if not authenticated
- **Client-side only guard** — no server-side enforcement

#### `api.js`
- Axios interceptor catches 401 → attempts `/auth/refresh` → redirects to `/login?expired=true`
- No JWT tokens sent in headers
- Uses Vite proxy: `/api/*` → `http://127.0.0.1:8000/*` (strips `/api`), `/auth/*` → `http://127.0.0.1:8000/auth/*`

#### `Login.jsx`
- Redirects to `http://localhost:8000/auth/google/login` (hardcoded URL)
- On mount, checks `checkAuth()` — if already authenticated, navigates to `/`

### Dependencies
- `fastapi` — HTTP framework, supports `Depends()` DI
- `requests` — Used for Google API calls
- No JWT library currently installed (`PyJWT` or `python-jose` needed)

## Design Decisions

### Separation of Concerns: Google Token vs App JWT
1. **Google OAuth token** — Used only server-side to call YouTube APIs. Stored per-user in a database/store, never exposed to frontend.
2. **App JWT token** — Issued by our server after successful Google OAuth. Sent to frontend as HTTP-only cookie or bearer token. Contains user ID, expiry.

### Multi-User Token Storage
- Replace `oauth.json` flat file with per-user storage (TinyDB or similar)
- Key by Google user ID (from `channels?mine=true` or `userinfo` endpoint)
- Store Google tokens server-side, keyed by user ID

### Route Protection Strategy
- FastAPI `Depends()` middleware that extracts + validates JWT from request
- All non-auth routes require valid JWT
- JWT payload contains user ID → used as `owner` for data queries
- No more client-supplied `owner` parameter

## Technologies Needed
| Technology | Purpose | Notes |
|------------|---------|-------|
| `PyJWT` | JWT creation/verification | Lightweight, pure Python |
| `secrets` (stdlib) | JWT secret key generation | For `JWT_SECRET` env var |
| TinyDB (existing) | Per-user Google token storage | Already a dependency |
