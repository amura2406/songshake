"""Integration tests for FirestoreJobsAdapter against Firebase emulator.

Run with:
    firebase emulators:start --only firestore &
    FIRESTORE_EMULATOR_HOST=localhost:8081 uv run pytest src/song_shake/platform/test_firestore_jobs_integration.py -v
"""

from song_shake.features.jobs.models import JobType


class TestFirestoreJobsAdapter:
    """Integration tests for FirestoreJobsAdapter (JobStoragePort)."""

    def test_create_and_get_job(self, jobs_adapter):
        """Should create a job and retrieve it by ID."""
        job = jobs_adapter.create_job(
            job_id="job_1", job_type=JobType.ENRICHMENT,
            playlist_id="PL1", owner="owner_1", playlist_name="My Playlist",
        )

        assert job["id"] == "job_1"
        assert job["status"] == "pending"

        retrieved = jobs_adapter.get_job("job_1")
        assert retrieved is not None
        assert retrieved["playlist_name"] == "My Playlist"

    def test_update_job(self, jobs_adapter):
        """Should partially update job fields."""
        jobs_adapter.create_job(
            job_id="job_up", job_type=JobType.ENRICHMENT,
            playlist_id="PL1", owner="o",
        )

        jobs_adapter.update_job("job_up", {
            "status": "running", "current": 5, "total": 10,
        })

        job = jobs_adapter.get_job("job_up")
        assert job["status"] == "running"
        assert job["current"] == 5
        assert job["total"] == 10

    def test_get_active_jobs(self, jobs_adapter):
        """Should return only pending/running jobs."""
        jobs_adapter.create_job("j1", JobType.ENRICHMENT, "PL1", "o")
        jobs_adapter.create_job("j2", JobType.ENRICHMENT, "PL2", "o")
        jobs_adapter.update_job("j2", {"status": "completed"})

        active = jobs_adapter.get_active_jobs("o")
        assert len(active) == 1
        assert active[0]["id"] == "j1"

    def test_get_job_history(self, jobs_adapter):
        """Should return only terminal-status jobs."""
        jobs_adapter.create_job("j1", JobType.ENRICHMENT, "PL1", "o")
        jobs_adapter.create_job("j2", JobType.ENRICHMENT, "PL2", "o")
        jobs_adapter.update_job("j1", {"status": "completed"})

        history = jobs_adapter.get_job_history("o")
        assert len(history) == 1
        assert history[0]["id"] == "j1"

    def test_get_job_for_playlist(self, jobs_adapter):
        """Should return an active job for a specific playlist."""
        jobs_adapter.create_job("j1", JobType.ENRICHMENT, "PL1", "o")

        found = jobs_adapter.get_job_for_playlist("PL1", "o")
        assert found is not None
        assert found["id"] == "j1"

        assert jobs_adapter.get_job_for_playlist("PL_nonexistent", "o") is None

    def test_check_and_create_job_prevents_duplicates(self, jobs_adapter):
        """Should return None if an active job already exists for the playlist."""
        result1 = jobs_adapter.check_and_create_job(
            "PL1", "o", "j1", JobType.ENRICHMENT, "My PL",
        )
        assert result1 is not None

        result2 = jobs_adapter.check_and_create_job(
            "PL1", "o", "j2", JobType.ENRICHMENT, "My PL",
        )
        assert result2 is None

    def test_check_and_create_job_allows_after_completion(self, jobs_adapter):
        """Should allow creating a new job after previous one completed."""
        jobs_adapter.check_and_create_job("PL1", "o", "j1", JobType.ENRICHMENT)
        jobs_adapter.update_job("j1", {"status": "completed"})

        result = jobs_adapter.check_and_create_job("PL1", "o", "j2", JobType.ENRICHMENT)
        assert result is not None
        assert result["id"] == "j2"

    def test_get_all_active_jobs(self, jobs_adapter):
        """Should return playlist_id→job mapping for all active jobs."""
        jobs_adapter.create_job("j1", JobType.ENRICHMENT, "PL1", "alice")
        jobs_adapter.create_job("j2", JobType.ENRICHMENT, "PL2", "bob")

        mapping = jobs_adapter.get_all_active_jobs()
        assert "PL1" in mapping
        assert "PL2" in mapping

    def test_ai_usage_crud(self, jobs_adapter):
        """Should create, read, and increment AI usage."""
        usage = jobs_adapter.get_ai_usage("owner_1")
        assert usage["input_tokens"] == 0
        assert usage["cost"] == 0.0

        updated = jobs_adapter.update_ai_usage("owner_1", 100, 50, 0.01)
        assert updated["input_tokens"] == 100
        assert updated["output_tokens"] == 50
        assert updated["cost"] == 0.01

        # Incremental update
        updated2 = jobs_adapter.update_ai_usage("owner_1", 200, 100, 0.02)
        assert updated2["input_tokens"] == 300
        assert updated2["output_tokens"] == 150
        assert abs(updated2["cost"] - 0.03) < 0.001

    def test_get_job_returns_none_for_missing(self, jobs_adapter):
        """Should return None for a nonexistent job."""
        assert jobs_adapter.get_job("nonexistent") is None
