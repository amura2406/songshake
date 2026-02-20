"""Integration tests for FirestoreSongsAdapter against Firebase emulator.

Run with:
    firebase emulators:start --only firestore &
    FIRESTORE_EMULATOR_HOST=localhost:8081 uv run pytest src/song_shake/platform/test_firestore_songs_integration.py -v
"""


class TestFirestoreSongsAdapter:
    """Integration tests for FirestoreSongsAdapter (StoragePort)."""

    def test_save_and_get_track(self, songs_adapter):
        """Should persist a track and retrieve it by owner."""
        track = {
            "videoId": "test_vid_1",
            "title": "Integration Test Song",
            "artists": "Test Artist",
            "owner": "owner_1",
            "status": "success",
            "genres": ["Rock"],
            "moods": ["Energetic"],
            "instruments": ["Guitar"],
            "bpm": 120,
        }
        songs_adapter.save_track(track)

        tracks = songs_adapter.get_all_tracks("owner_1")
        assert len(tracks) == 1
        assert tracks[0]["videoId"] == "test_vid_1"
        assert tracks[0]["title"] == "Integration Test Song"

    def test_get_track_by_id(self, songs_adapter):
        """Should retrieve a track from the global catalog by videoId."""
        track = {"videoId": "vid_by_id", "title": "By ID", "owner": "o1", "status": "success"}
        songs_adapter.save_track(track)

        result = songs_adapter.get_track_by_id("vid_by_id")
        assert result is not None
        assert result["title"] == "By ID"

        assert songs_adapter.get_track_by_id("nonexistent") is None

    def test_tracks_isolated_by_owner(self, songs_adapter):
        """Different owners should see only their own tracks."""
        songs_adapter.save_track({"videoId": "v1", "title": "T1", "owner": "alice", "status": "success"})
        songs_adapter.save_track({"videoId": "v2", "title": "T2", "owner": "bob", "status": "success"})

        alice_tracks = songs_adapter.get_all_tracks("alice")
        bob_tracks = songs_adapter.get_all_tracks("bob")

        assert len(alice_tracks) == 1
        assert alice_tracks[0]["videoId"] == "v1"
        assert len(bob_tracks) == 1
        assert bob_tracks[0]["videoId"] == "v2"

    def test_track_deduplication_by_video_id(self, songs_adapter):
        """Saving same videoId twice should update, not duplicate."""
        songs_adapter.save_track({"videoId": "dup1", "title": "V1", "owner": "o", "status": "success"})
        songs_adapter.save_track({"videoId": "dup1", "title": "V1 Updated", "owner": "o", "status": "success"})

        tracks = songs_adapter.get_all_tracks("o")
        assert len(tracks) == 1
        assert tracks[0]["title"] == "V1 Updated"

    def test_get_tags(self, songs_adapter):
        """Should aggregate genres, moods, instruments, and statuses."""
        songs_adapter.save_track({
            "videoId": "t1", "owner": "o", "status": "success",
            "genres": ["Rock", "Pop"], "moods": ["Happy"], "instruments": ["Guitar"],
        })
        songs_adapter.save_track({
            "videoId": "t2", "owner": "o", "status": "error",
            "genres": ["Rock"], "moods": [], "instruments": [],
        })

        tags = songs_adapter.get_tags("o")
        tag_names = {t["name"] for t in tags}

        assert "Rock" in tag_names
        assert "Pop" in tag_names
        assert "Happy" in tag_names
        assert "Success" in tag_names
        assert "Failed" in tag_names

        rock = next(t for t in tags if t["name"] == "Rock")
        assert rock["count"] == 2

    def test_get_failed_tracks(self, songs_adapter):
        """Should return only error-status tracks."""
        songs_adapter.save_track({"videoId": "ok", "owner": "o", "status": "success"})
        songs_adapter.save_track({"videoId": "fail", "owner": "o", "status": "error"})

        failed = songs_adapter.get_failed_tracks("o")
        assert len(failed) == 1
        assert failed[0]["videoId"] == "fail"

    def test_enrichment_history_crud(self, songs_adapter):
        """Should save and retrieve enrichment history per owner."""
        songs_adapter.save_enrichment_history("PL1", "owner_1", {
            "last_processed": "2026-02-20T00:00:00",
            "status": "completed",
        })

        history = songs_adapter.get_enrichment_history("owner_1")
        assert "PL1" in history
        assert history["PL1"]["status"] == "completed"

    def test_get_all_history(self, songs_adapter):
        """Should return history across all owners."""
        songs_adapter.save_enrichment_history("PL1", "alice", {"status": "completed"})
        songs_adapter.save_enrichment_history("PL2", "bob", {"status": "error"})

        all_history = songs_adapter.get_all_history()
        assert "PL1" in all_history
        assert "PL2" in all_history

    def test_task_state_crud(self, songs_adapter):
        """Should persist and retrieve task state."""
        songs_adapter.save_task_state("task_1", {"status": "running", "current": 5, "total": 10})

        state = songs_adapter.get_task_state("task_1")
        assert state is not None
        assert state["status"] == "running"
        assert state["current"] == 5

        assert songs_adapter.get_task_state("nonexistent") is None

    def test_wipe_db(self, songs_adapter):
        """Should delete all documents in all collections."""
        songs_adapter.save_track({"videoId": "v1", "owner": "o", "status": "success"})
        songs_adapter.save_enrichment_history("PL1", "o", {"status": "completed"})
        songs_adapter.save_task_state("t1", {"status": "running"})

        songs_adapter.wipe_db()

        assert songs_adapter.get_all_tracks("o") == []
        assert songs_adapter.get_all_history() == {}
        assert songs_adapter.get_task_state("t1") is None
