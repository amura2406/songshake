# Suggested Commands

## Installation
- Install globally: `uv tool install . --force`
- Upgrade: `uv tool upgrade song-shake`

## Usage
- Setup Auth: `song-shake setup-auth`
- List Playlists: `song-shake list-playlists`
- Enrich Playlist: `song-shake enrich <PLAYLIST_ID> [--wipe]`
- Show Results: `song-shake show [--limit 100] [--genre "Pop"] [--mood "Chill"]`

## Development
- format: `ruff format .` (Suggested, not enforced)
- lint: `ruff check .` (Suggested, not enforced)
- run: `uv run song-shake ...`