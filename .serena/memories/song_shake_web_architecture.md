# Song Shake Web Architecture & Implementation

## Overview
Added a React/Vite frontend to the existing CLI tool to provide a GUI for playlist enrichment.

## Authentication
- **Mechanism**: Google OAuth 2.0 Device Code Flow.
- **Reason**: YouTube Music does not support standard "Web" OAuth flow easily for this type of private API access without a verified app, and manual header copying is bad UX. Device flow allows users to auth via `google.com/device`.
- **Endpoints**:
  - `POST /auth/google/init`: Returns `device_code`, `user_code`, `verification_url`.
  - `POST /auth/google/poll`: polls for token validity.
- **Storage**: Tokens saved to `oauth.json` (compatible with `ytmusicapi`).

## Real-time Updates
- **Mechanism**: Server-Sent Events (SSE).
- **Endpoint**: `GET /enrichment/stream/{task_id}`.
- **Usage**: content streams JSON status updates (`current`, `total`, `message`) to the frontend `Enrichment` component.

## Database
- **Schema**: `songs.db` (TinyDB).
- **New Fields**: 
  - `owner`: to segregate web users (default `web_user`).
  - `url`: direct link to YouTube Music.
  - `thumbnails`: allowed for cover art display.

## Frontend Components
- **Login**: Handles Device Code flow.
- **Dashboard**: Lists playlists.
- **Enrichment**: SSE connection and progress bar.
- **Results**: Grid view of songs + Fixed Bottom Player (YouTube IFrame).
