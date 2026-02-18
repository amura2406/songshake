"""Unit tests for enrichment route handlers."""

from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from song_shake.api import app
from song_shake.features.enrichment.routes import enrichment_tasks

client = TestClient(app)


# --- Helpers ---


@pytest.fixture(autouse=True)
def _clear_enrichment_tasks():
    """Clear in-memory enrichment tasks before each test."""
    enrichment_tasks.clear()
    yield
    enrichment_tasks.clear()


# --- start_enrichment tests ---


class TestStartEnrichment:
    """Tests for POST /enrichment."""

    @patch("song_shake.features.enrichment.routes.os.urandom")
    @patch("song_shake.features.enrichment.routes.os.getenv")
    def test_starts_enrichment_with_request_api_key(self, mock_getenv, mock_urandom):
        """Should start enrichment when API key is provided in request."""
        mock_getenv.return_value = None  # No env var
        mock_urandom.return_value = b"\xaa\xbb\xcc\xdd"

        response = client.post(
            "/enrichment",
            json={
                "playlist_id": "PL_test",
                "owner": "test_user",
                "api_key": "test-key-123",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert data["task_id"].startswith("PL_test_")

    @patch("song_shake.features.enrichment.routes._persist_task")
    @patch("song_shake.features.enrichment.routes.os.urandom")
    @patch("song_shake.features.enrichment.routes.os.getenv")
    def test_starts_enrichment_with_env_api_key(
        self, mock_getenv, mock_urandom, mock_persist
    ):
        """Should fall back to env var when no API key in request."""
        mock_getenv.side_effect = lambda key: (
            "env-key-456" if key == "GOOGLE_API_KEY" else None
        )
        mock_urandom.return_value = b"\xaa\xbb\xcc\xdd"

        response = client.post(
            "/enrichment",
            json={"playlist_id": "PL_test"},
        )

        assert response.status_code == 200

    def test_returns_400_when_no_api_key(self):
        """Should return 400 when no API key is available."""
        with patch("song_shake.features.enrichment.routes.os.getenv", return_value=None):
            response = client.post(
                "/enrichment",
                json={"playlist_id": "PL_test"},
            )

        assert response.status_code == 400
        assert "API Key required" in response.json()["detail"]

    @patch("song_shake.features.enrichment.routes._persist_task")
    @patch("song_shake.features.enrichment.routes.os.urandom")
    @patch("song_shake.features.enrichment.routes.os.getenv")
    def test_creates_initial_task_state(self, mock_getenv, mock_urandom, mock_persist):
        """Should create initial task state in memory."""
        mock_getenv.return_value = "test-key"
        mock_urandom.return_value = b"\x01\x02\x03\x04"

        # Prevent the background task from running synchronously in TestClient
        with patch("song_shake.features.enrichment.routes.BackgroundTasks.add_task"):
            response = client.post(
                "/enrichment",
                json={"playlist_id": "PL_test"},
            )

        task_id = response.json()["task_id"]
        assert task_id in enrichment_tasks
        assert enrichment_tasks[task_id]["status"] == "pending"
        assert enrichment_tasks[task_id]["total"] == 0


# --- get_enrichment_status tests ---


class TestGetEnrichmentStatus:
    """Tests for GET /enrichment/status/{task_id}."""

    def test_returns_in_memory_task(self):
        """Should return task from in-memory dict."""
        enrichment_tasks["task_123"] = {
            "status": "running",
            "total": 10,
            "current": 5,
            "message": "Processing...",
            "results": [],
        }

        response = client.get("/enrichment/status/task_123")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"
        assert data["current"] == 5

    @patch("song_shake.features.enrichment.routes.storage.get_task_state")
    def test_falls_back_to_persistent_storage(self, mock_get_state):
        """Should check persistent storage when task not in memory."""
        mock_get_state.return_value = {
            "task_id": "old_task",
            "status": "completed",
            "message": "Done",
        }

        response = client.get("/enrichment/status/old_task")

        assert response.status_code == 200
        assert response.json()["status"] == "completed"

    @patch("song_shake.features.enrichment.routes.storage.get_task_state")
    def test_returns_404_when_not_found(self, mock_get_state):
        """Should return 404 when task doesn't exist anywhere."""
        mock_get_state.return_value = None

        response = client.get("/enrichment/status/nonexistent")

        assert response.status_code == 404


# --- stream_enrichment_status tests ---


class TestStreamEnrichmentStatus:
    """Tests for GET /enrichment/stream/{task_id}."""

    def test_returns_404_for_unknown_task(self):
        """Should return 404 when task not in memory."""
        response = client.get("/enrichment/stream/nonexistent")

        assert response.status_code == 404

    def test_streams_completed_task(self):
        """Should stream status and stop when task completes."""
        enrichment_tasks["task_done"] = {
            "status": "completed",
            "total": 10,
            "current": 10,
            "message": "Done",
            "tokens": 1000,
            "cost": 0.01,
        }

        response = client.get("/enrichment/stream/task_done")

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        # Should contain at least one data event
        assert "data:" in response.text
