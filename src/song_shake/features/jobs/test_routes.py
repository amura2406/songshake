"""Unit tests for jobs route handlers."""

from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from song_shake.api import app

client = TestClient(app)


# --- Helpers ---


@pytest.fixture(autouse=True)
def _clean_job_state():
    """Reset in-memory state and clean DB tables between tests."""
    from song_shake.features.jobs import logic

    logic._cancel_events.clear()
    logic._job_live_state.clear()
    logic._ai_usage_live.clear()
    yield
    logic._cancel_events.clear()
    logic._job_live_state.clear()
    logic._ai_usage_live.clear()


# --- create_job tests ---


class TestCreateJob:
    """Tests for POST /jobs."""

    @patch("song_shake.features.jobs.routes.os.urandom")
    @patch("song_shake.features.jobs.routes.os.getenv")
    @patch("song_shake.features.jobs.storage.check_and_create_job")
    def test_creates_job_with_api_key(
        self, mock_check_create, mock_getenv, mock_urandom
    ):
        """Should create a job when API key is provided."""
        mock_getenv.return_value = None
        mock_urandom.return_value = b"\xaa\xbb\xcc\xdd"
        mock_check_create.return_value = {
            "id": "job_PL_test_aabbccdd",
            "type": "enrichment",
            "playlist_id": "PL_test",
            "owner": "test_user",
            "status": "pending",
            "total": 0,
            "current": 0,
            "message": "Initializing…",
            "errors": [],
            "ai_usage": {"input_tokens": 0, "output_tokens": 0, "cost": 0.0},
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
        }

        response = client.post(
            "/jobs",
            json={
                "playlist_id": "PL_test",
                "owner": "test_user",
                "api_key": "test-key-123",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "job_PL_test_aabbccdd"
        assert data["status"] == "pending"

    @patch("song_shake.features.jobs.routes.os.getenv")
    def test_returns_400_when_no_api_key(self, mock_getenv):
        """Should return 400 when no API key is available."""
        mock_getenv.return_value = None

        response = client.post(
            "/jobs",
            json={"playlist_id": "PL_test"},
        )

        assert response.status_code == 400
        assert "API Key required" in response.json()["detail"]

    @patch("song_shake.features.jobs.routes.os.getenv")
    @patch("song_shake.features.jobs.storage.check_and_create_job")
    def test_returns_409_when_duplicate_active_job(self, mock_check_create, mock_getenv):
        """Should return 409 when an active job already exists for this playlist."""
        mock_getenv.return_value = "test-key"
        mock_check_create.return_value = None  # Indicates duplicate found

        response = client.post(
            "/jobs",
            json={"playlist_id": "PL_test"},
        )

        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]


# --- get_job tests ---


class TestGetJob:
    """Tests for GET /jobs/{job_id}."""

    def test_returns_live_state(self):
        """Should return job from live in-memory state."""
        from song_shake.features.jobs import logic

        logic._job_live_state["job_123"] = {
            "id": "job_123",
            "status": "running",
            "total": 10,
            "current": 5,
            "message": "Processing...",
            "errors": [],
            "ai_usage": {"input_tokens": 100, "output_tokens": 50, "cost": 0.001},
        }

        response = client.get("/jobs/job_123")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"
        assert data["current"] == 5

    @patch("song_shake.features.jobs.storage.get_job")
    def test_falls_back_to_persistent_storage(self, mock_get_job):
        """Should check DB when job not in live state."""
        mock_get_job.return_value = {
            "id": "old_job",
            "status": "completed",
            "message": "Done",
        }

        response = client.get("/jobs/old_job")

        assert response.status_code == 200
        assert response.json()["status"] == "completed"

    @patch("song_shake.features.jobs.storage.get_job")
    def test_returns_404_when_not_found(self, mock_get_job):
        """Should return 404 when job doesn't exist."""
        mock_get_job.return_value = None

        response = client.get("/jobs/nonexistent")

        assert response.status_code == 404


# --- cancel_job tests ---


class TestCancelJob:
    """Tests for POST /jobs/{job_id}/cancel."""

    def test_cancels_running_job(self):
        """Should set cancel event for active job."""
        import threading
        from song_shake.features.jobs import logic

        event = threading.Event()
        logic._cancel_events["job_to_cancel"] = event

        response = client.post("/jobs/job_to_cancel/cancel")

        assert response.status_code == 200
        assert event.is_set()

    @patch("song_shake.features.jobs.storage.get_job")
    def test_returns_404_for_unknown_job(self, mock_get_job):
        """Should return 404 when job not found."""
        mock_get_job.return_value = None

        response = client.post("/jobs/nonexistent/cancel")

        assert response.status_code == 404

    @patch("song_shake.features.jobs.storage.get_job")
    def test_returns_409_for_finished_job(self, mock_get_job):
        """Should return 409 when job already finished."""
        mock_get_job.return_value = {"id": "done_job", "status": "completed"}

        response = client.post("/jobs/done_job/cancel")

        assert response.status_code == 409


# --- list_jobs tests ---


class TestListJobs:
    """Tests for GET /jobs."""

    @patch("song_shake.features.jobs.storage.get_active_jobs")
    def test_lists_active_jobs(self, mock_active):
        """Should return active jobs when status=active."""
        mock_active.return_value = [
            {"id": "j1", "status": "running", "playlist_id": "PL1"}
        ]

        response = client.get("/jobs?status=active")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "j1"

    @patch("song_shake.features.jobs.storage.get_job_history")
    def test_lists_job_history(self, mock_history):
        """Should return history when status=history."""
        mock_history.return_value = [
            {"id": "j2", "status": "completed", "playlist_id": "PL2"}
        ]

        response = client.get("/jobs?status=history")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "completed"


# --- stream_job tests ---


class TestStreamJob:
    """Tests for GET /jobs/{job_id}/stream."""

    @patch("song_shake.features.jobs.storage.get_job")
    def test_returns_404_for_unknown_job(self, mock_get_job):
        """Should return 404 when job not found anywhere."""
        mock_get_job.return_value = None

        response = client.get("/jobs/nonexistent/stream")

        assert response.status_code == 404

    def test_streams_completed_job(self):
        """Should stream status and stop when job is terminal."""
        from song_shake.features.jobs import logic

        logic._job_live_state["job_done"] = {
            "id": "job_done",
            "status": "completed",
            "total": 10,
            "current": 10,
            "message": "Done",
            "errors": [],
            "ai_usage": {"input_tokens": 500, "output_tokens": 200, "cost": 0.01},
        }

        response = client.get("/jobs/job_done/stream")

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        assert "data:" in response.text
