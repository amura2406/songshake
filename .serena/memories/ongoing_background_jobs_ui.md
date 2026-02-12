# UI Fix: Active Background Jobs

## Summary
The UI was updated to support visualizing ongoing background jobs on the Dashboard without allowing the user to start a duplicate job. 
When a playlist is actively being processed, its card on the Dashboard will:
- Display an "In Progress" / pulsing interface
- Show a "View Progress" button instead of "Identify Songs"
- Instantly navigate to the ongoing `task_id`'s progress screen when clicked.

## Key Changes
- **Backend**: `api.py` `get_playlists` endpoint was modified. It parses the in-memory `enrichment_tasks` dictionary to find running tasks and attaches `is_running: True` and `active_task_id` to the returned payload. 
  - *Note*: Added `is_running` and `active_task_id` to `PlaylistResponse` Pydantic model so FastAPI stops stripping it out of the response.
- **Frontend**: 
  - `web/src/components/Dashboard.jsx` handles passing the playlist object and checking `playlist.is_running`.
  - Added a 5-second `setInterval` polling mechanism to refresh the Dashboard in the background, ensuring jobs started in other tabs or sessions show up quickly.