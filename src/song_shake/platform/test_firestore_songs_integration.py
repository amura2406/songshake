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
            "timestamp": "2026-02-20T00:00:00",
            "item_count": 5,
            "status": "completed",
        })

        history = songs_adapter.get_enrichment_history("owner_1")
        assert "PL1" in history
        assert history["PL1"]["status"] == "completed"
        assert history["PL1"]["last_processed"] == "2026-02-20T00:00:00"
        assert history["PL1"]["item_count"] == 5

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

    def test_delete_tracks_removes_ownership_and_orphan(self, songs_adapter):
        """Should delete both track_owners and orphaned tracks docs."""
        songs_adapter.save_track({"videoId": "del1", "owner": "alice", "status": "success", "title": "Del1"})
        songs_adapter.save_track({"videoId": "del2", "owner": "alice", "status": "success", "title": "Del2"})

        deleted = songs_adapter.delete_tracks("alice", ["del1", "del2"])

        assert deleted == 2
        assert songs_adapter.get_all_tracks("alice") == []
        # Orphaned global docs should also be gone
        assert songs_adapter.get_track_by_id("del1") is None
        assert songs_adapter.get_track_by_id("del2") is None

    def test_delete_tracks_preserves_shared_track(self, songs_adapter):
        """Shared track should survive when one owner deletes."""
        songs_adapter.save_track({"videoId": "shared1", "owner": "alice", "status": "success", "title": "Shared"})
        songs_adapter.save_track({"videoId": "shared1", "owner": "bob", "status": "success", "title": "Shared"})

        deleted = songs_adapter.delete_tracks("alice", ["shared1"])

        assert deleted == 1
        assert songs_adapter.get_all_tracks("alice") == []
        # Bob still sees it
        bob_tracks = songs_adapter.get_all_tracks("bob")
        assert len(bob_tracks) == 1
        assert bob_tracks[0]["videoId"] == "shared1"
        # Global catalog preserved
        assert songs_adapter.get_track_by_id("shared1") is not None

    def test_delete_tracks_empty_list(self, songs_adapter):
        """Should return 0 for empty video_ids list."""
        assert songs_adapter.delete_tracks("alice", []) == 0

    # --- tag counts ---

    def test_tag_counts_updated_on_save(self, songs_adapter):
        """Should maintain pre-computed tag counts when saving tracks."""
        songs_adapter.save_track({
            "videoId": "tc1", "owner": "o", "status": "success",
            "genres": ["Rock", "Pop"], "moods": ["Happy"], "instruments": ["Guitar"],
        })
        songs_adapter.save_track({
            "videoId": "tc2", "owner": "o", "status": "error",
            "genres": ["Rock"], "moods": [], "instruments": [],
        })

        counts = songs_adapter.get_tag_counts("o")
        assert counts.get("total") == 2
        assert counts.get("genres.Rock") == 2
        assert counts.get("genres.Pop") == 1
        assert counts.get("moods.Happy") == 1
        assert counts.get("status.Success") == 1
        assert counts.get("status.Failed") == 1

    def test_tag_counts_decremented_on_delete(self, songs_adapter):
        """Should decrement tag counts when tracks are deleted."""
        songs_adapter.save_track({
            "videoId": "td1", "owner": "o", "status": "success",
            "genres": ["Rock"], "moods": ["Energetic"], "instruments": [],
        })
        songs_adapter.save_track({
            "videoId": "td2", "owner": "o", "status": "success",
            "genres": ["Rock", "Pop"], "moods": [], "instruments": [],
        })

        # Delete one track
        songs_adapter.delete_tracks("o", ["td1"])

        counts = songs_adapter.get_tag_counts("o")
        assert counts.get("genres.Rock") == 1  # was 2, now 1
        assert counts.get("genres.Pop") == 1  # unchanged
        # Energetic was only on td1, now 0 (may still be key with 0)
        assert counts.get("moods.Energetic", 0) <= 0

    def test_tag_counts_handles_track_update(self, songs_adapter):
        """Should adjust tag counts when a track's tags are updated."""
        songs_adapter.save_track({
            "videoId": "tu1", "owner": "o", "status": "success",
            "genres": ["Rock"], "moods": [], "instruments": [],
        })
        counts_before = songs_adapter.get_tag_counts("o")
        assert counts_before.get("genres.Rock") == 1

        # Update genres from Rock to Pop
        songs_adapter.save_track({
            "videoId": "tu1", "owner": "o", "status": "success",
            "genres": ["Pop"], "moods": [], "instruments": [],
        })
        counts_after = songs_adapter.get_tag_counts("o")
        assert counts_after.get("genres.Rock", 0) <= 0  # Rock removed
        assert counts_after.get("genres.Pop") == 1  # Pop added
        assert counts_after.get("total") == 1  # Still 1 track, not 2

    def test_rebuild_tag_counts(self, songs_adapter):
        """Should rebuild tag counts from scratch via full scan."""
        songs_adapter.save_track({
            "videoId": "rb1", "owner": "o", "status": "success",
            "genres": ["Jazz"], "moods": ["Calm"], "instruments": [],
        })
        songs_adapter.save_track({
            "videoId": "rb2", "owner": "o", "status": "success",
            "genres": ["Jazz", "Blues"], "moods": [], "instruments": [],
        })

        rebuilt = songs_adapter.rebuild_tag_counts("o")
        assert rebuilt["total"] == 2
        assert rebuilt["genres.Jazz"] == 2
        assert rebuilt["genres.Blues"] == 1
        assert rebuilt.get("moods.Calm") == 1

    def test_tag_counts_empty_for_unknown_owner(self, songs_adapter):
        """Should return empty dict for owner with no tracks."""
        counts = songs_adapter.get_tag_counts("nobody")
        assert counts == {}

    # --- paginated tracks ---

    def test_paginated_tracks_returns_page(self, songs_adapter):
        """Should return only requested number of tracks."""
        for i in range(5):
            songs_adapter.save_track({
                "videoId": f"pg{i}", "owner": "o", "status": "success",
                "title": f"Track {i}",
            })

        tracks, next_cursor = songs_adapter.get_paginated_tracks("o", limit=3)
        assert len(tracks) == 3
        assert next_cursor is not None

    def test_paginated_tracks_cursor_navigation(self, songs_adapter):
        """Should navigate to second page using cursor."""
        for i in range(5):
            songs_adapter.save_track({
                "videoId": f"nav{i:02d}", "owner": "o", "status": "success",
                "title": f"Track {i}",
            })

        page1, cursor1 = songs_adapter.get_paginated_tracks("o", limit=3)
        assert len(page1) == 3
        assert cursor1 is not None

        page2, cursor2 = songs_adapter.get_paginated_tracks("o", limit=3, start_after=cursor1)
        assert len(page2) == 2  # remaining 2 tracks
        assert cursor2 is None  # last page
        # No duplicates across pages
        page1_ids = {t["videoId"] for t in page1}
        page2_ids = {t["videoId"] for t in page2}
        assert page1_ids.isdisjoint(page2_ids)

    def test_paginated_tracks_last_page(self, songs_adapter):
        """Should return next_cursor=None on the last page."""
        songs_adapter.save_track({"videoId": "lp1", "owner": "o", "status": "success"})

        tracks, cursor = songs_adapter.get_paginated_tracks("o", limit=10)
        assert len(tracks) == 1
        assert cursor is None

    def test_paginated_tracks_empty(self, songs_adapter):
        """Should return empty list for owner with no tracks."""
        tracks, cursor = songs_adapter.get_paginated_tracks("nobody", limit=10)
        assert tracks == []
        assert cursor is None
