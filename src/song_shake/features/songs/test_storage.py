"""Unit tests for storage module."""

import os
import tempfile

import pytest
from tinydb import TinyDB

from song_shake.features.songs import storage


@pytest.fixture
def tmp_db():
    """Create a temporary TinyDB database for testing."""
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    db = TinyDB(path)
    yield db
    db.close()
    os.unlink(path)


@pytest.fixture
def tmp_db_path():
    """Create a temporary db file path for tests that use storage module functions."""
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


class TestSaveTrack:
    """Tests for save_track()."""

    def test_save_and_retrieve_track(self, tmp_db):
        """Should save a track to the global catalog and link it to an owner."""
        track = {
            "videoId": "abc123",
            "title": "Test Song",
            "artists": "Test Artist",
            "genres": ["Rock"],
            "moods": ["Energetic"],
            "status": "success",
            "owner": "test_user",
        }

        storage.save_track(tmp_db, track)

        tracks = storage.get_all_tracks(tmp_db, owner="test_user")
        assert len(tracks) == 1
        assert tracks[0]["videoId"] == "abc123"
        assert tracks[0]["title"] == "Test Song"

    def test_save_track_strips_owner_from_global_catalog(self, tmp_db):
        """Owner should be stripped from the global songs table."""
        track = {
            "videoId": "abc123",
            "title": "Test Song",
            "artists": "Test Artist",
            "status": "success",
            "owner": "test_user",
        }

        storage.save_track(tmp_db, track)

        songs_table = tmp_db.table("songs")
        all_songs = songs_table.all()
        assert len(all_songs) == 1
        assert "owner" not in all_songs[0]

    def test_save_track_deduplicates_by_video_id(self, tmp_db):
        """Saving the same videoId twice should upsert, not duplicate."""
        track1 = {
            "videoId": "abc123",
            "title": "Old Title",
            "artists": "Artist",
            "status": "success",
            "owner": "user1",
        }
        track2 = {
            "videoId": "abc123",
            "title": "New Title",
            "artists": "Artist",
            "status": "success",
            "owner": "user1",
        }

        storage.save_track(tmp_db, track1)
        storage.save_track(tmp_db, track2)

        songs = tmp_db.table("songs").all()
        assert len(songs) == 1
        assert songs[0]["title"] == "New Title"

    def test_save_track_different_owners_share_global_song(self, tmp_db):
        """Two owners saving the same videoId should share a single global record."""
        track_user1 = {
            "videoId": "abc123",
            "title": "Song",
            "artists": "Artist",
            "status": "success",
            "owner": "user1",
        }
        track_user2 = {
            "videoId": "abc123",
            "title": "Song",
            "artists": "Artist",
            "status": "success",
            "owner": "user2",
        }

        storage.save_track(tmp_db, track_user1)
        storage.save_track(tmp_db, track_user2)

        # Only one global song
        assert len(tmp_db.table("songs").all()) == 1

        # Both users linked
        assert len(storage.get_all_tracks(tmp_db, "user1")) == 1
        assert len(storage.get_all_tracks(tmp_db, "user2")) == 1


class TestGetAllTracks:
    """Tests for get_all_tracks()."""

    def test_returns_empty_for_unknown_owner(self, tmp_db):
        """Should return empty list for an owner with no tracks."""
        tracks = storage.get_all_tracks(tmp_db, owner="nonexistent")
        assert tracks == []

    def test_returns_only_owned_tracks(self, tmp_db):
        """Should only return tracks linked to the specified owner."""
        for i, owner in enumerate(["user1", "user1", "user2"]):
            storage.save_track(
                tmp_db,
                {
                    "videoId": f"vid{i}",
                    "title": f"Song {i}",
                    "artists": "Artist",
                    "status": "success",
                    "owner": owner,
                },
            )

        user1_tracks = storage.get_all_tracks(tmp_db, owner="user1")
        user2_tracks = storage.get_all_tracks(tmp_db, owner="user2")

        assert len(user1_tracks) == 2
        assert len(user2_tracks) == 1


class TestGetTags:
    """Tests for get_tags()."""

    def test_counts_genres_and_moods(self, tmp_db):
        """Should count occurrences of each genre and mood tag."""
        for i in range(3):
            storage.save_track(
                tmp_db,
                {
                    "videoId": f"vid{i}",
                    "title": f"Song {i}",
                    "artists": "Artist",
                    "genres": ["Rock"],
                    "moods": ["Happy"] if i < 2 else ["Sad"],
                    "instruments": [],
                    "status": "success",
                    "owner": "user1",
                },
            )

        tags = storage.get_tags(tmp_db, owner="user1")
        tag_map = {t["name"]: t for t in tags}

        assert tag_map["Rock"]["count"] == 3
        assert tag_map["Rock"]["type"] == "genre"
        assert tag_map["Happy"]["count"] == 2
        assert tag_map["Sad"]["count"] == 1

    def test_counts_success_and_failed_status(self, tmp_db):
        """Should include Success and Failed status counts."""
        storage.save_track(
            tmp_db,
            {
                "videoId": "v1",
                "title": "S1",
                "artists": "A",
                "status": "success",
                "owner": "user1",
            },
        )
        storage.save_track(
            tmp_db,
            {
                "videoId": "v2",
                "title": "S2",
                "artists": "A",
                "status": "error",
                "owner": "user1",
            },
        )

        tags = storage.get_tags(tmp_db, owner="user1")
        tag_map = {t["name"]: t for t in tags}

        assert tag_map["Success"]["count"] == 1
        assert tag_map["Failed"]["count"] == 1


class TestEnrichmentHistory:
    """Tests for enrichment history persistence."""

    def test_save_and_retrieve_history(self, tmp_db_path):
        """Should save and retrieve enrichment history for a playlist."""
        db = TinyDB(tmp_db_path)
        storage.save_enrichment_history(
            "PL_abc",
            "user1",
            {"timestamp": "2026-01-01T00:00:00", "item_count": 10, "status": "completed"},
            db=db,
        )

        history = storage.get_enrichment_history("user1", db=db)
        assert "PL_abc" in history
        assert history["PL_abc"]["last_processed"] == "2026-01-01T00:00:00"
        assert history["PL_abc"]["item_count"] == 10
        db.close()

    def test_history_upserts_on_same_playlist(self, tmp_db_path):
        """Should update existing history rather than creating duplicates."""
        db = TinyDB(tmp_db_path)
        storage.save_enrichment_history(
            "PL_abc", "user1", {"timestamp": "2026-01-01", "status": "completed"}, db=db
        )
        storage.save_enrichment_history(
            "PL_abc", "user1", {"timestamp": "2026-02-01", "status": "completed"}, db=db
        )

        history = storage.get_enrichment_history("user1", db=db)
        assert len(history) == 1
        assert history["PL_abc"]["last_processed"] == "2026-02-01"
        db.close()


class TestTaskState:
    """Tests for enrichment task state persistence (Group 4)."""

    def test_save_and_get_task_state(self, tmp_db_path):
        """Should persist and retrieve task state."""
        db = TinyDB(tmp_db_path)
        state = {"status": "running", "current": 5, "total": 10, "message": "Processing..."}
        storage.save_task_state("task_001", state, db=db)

        result = storage.get_task_state("task_001", db=db)
        assert result is not None
        assert result["task_id"] == "task_001"
        assert result["status"] == "running"
        assert result["current"] == 5
        db.close()

    def test_get_task_state_returns_none_for_unknown(self, tmp_db_path):
        """Should return None for a task that doesn't exist."""
        db = TinyDB(tmp_db_path)
        result = storage.get_task_state("nonexistent", db=db)
        assert result is None
        db.close()

    def test_save_task_state_upserts(self, tmp_db_path):
        """Should update existing task state rather than creating duplicates."""
        db = TinyDB(tmp_db_path)
        storage.save_task_state("task_001", {"status": "pending"}, db=db)
        storage.save_task_state("task_001", {"status": "completed"}, db=db)

        result = storage.get_task_state("task_001", db=db)
        assert result["status"] == "completed"

        tasks_table = db.table("tasks")
        assert len(tasks_table.all()) == 1
        db.close()

    def test_get_all_active_tasks(self, tmp_db_path):
        """Should return only pending/running tasks."""
        db = TinyDB(tmp_db_path)
        storage.save_task_state("t1", {"status": "pending"}, db=db)
        storage.save_task_state("t2", {"status": "running"}, db=db)
        storage.save_task_state("t3", {"status": "completed"}, db=db)
        storage.save_task_state("t4", {"status": "error"}, db=db)

        active = storage.get_all_active_tasks(db=db)
        assert len(active) == 2
        assert "t1" in active
        assert "t2" in active
        assert "t3" not in active
        assert "t4" not in active
        db.close()
