"""Unit tests for YouTube sync retry logic and complete_youtube_playlist."""

from unittest.mock import MagicMock, call, patch

import pytest

from song_shake.features.vibing.youtube_sync import (
    SyncResult,
    _fetch_existing_video_ids,
    _insert_with_retry,
    complete_youtube_playlist,
    create_youtube_playlist,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_response(status_code: int, json_data: dict | None = None, text: str = ""):
    """Create a mock requests.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text
    return resp


# ---------------------------------------------------------------------------
# _insert_with_retry
# ---------------------------------------------------------------------------


class TestInsertWithRetry:
    """Tests for the exponential-backoff insert helper."""

    @patch("song_shake.features.vibing.youtube_sync.time.sleep")
    @patch("song_shake.features.vibing.youtube_sync.requests.post")
    def test_success_on_first_attempt(self, mock_post, mock_sleep):
        """No retries needed when the first call succeeds."""
        mock_post.return_value = _mock_response(200)

        resp = _insert_with_retry({"Authorization": "Bearer tok"}, "PL1", "vid1")

        assert resp.status_code == 200
        assert mock_post.call_count == 1
        mock_sleep.assert_not_called()

    @patch("song_shake.features.vibing.youtube_sync.time.sleep")
    @patch("song_shake.features.vibing.youtube_sync.requests.post")
    def test_retry_on_409_then_success(self, mock_post, mock_sleep):
        """409 triggers retry, then succeeds on second attempt."""
        mock_post.side_effect = [
            _mock_response(409, text="aborted"),
            _mock_response(200),
        ]

        resp = _insert_with_retry(
            {"Authorization": "Bearer tok"}, "PL1", "vid1",
            max_retries=3, initial_backoff=1.0,
        )

        assert resp.status_code == 200
        assert mock_post.call_count == 2
        mock_sleep.assert_called_once_with(1.0)

    @patch("song_shake.features.vibing.youtube_sync.time.sleep")
    @patch("song_shake.features.vibing.youtube_sync.requests.post")
    def test_retry_on_503_then_success(self, mock_post, mock_sleep):
        """503 triggers retry with exponential backoff."""
        mock_post.side_effect = [
            _mock_response(503),
            _mock_response(503),
            _mock_response(200),
        ]

        resp = _insert_with_retry(
            {"Authorization": "Bearer tok"}, "PL1", "vid1",
            max_retries=3, initial_backoff=1.0,
        )

        assert resp.status_code == 200
        assert mock_post.call_count == 3
        # Backoff: 1.0, 2.0
        assert mock_sleep.call_args_list == [call(1.0), call(2.0)]

    @patch("song_shake.features.vibing.youtube_sync.time.sleep")
    @patch("song_shake.features.vibing.youtube_sync.requests.post")
    def test_exhausts_all_retries(self, mock_post, mock_sleep):
        """After max_retries, returns the last failed response."""
        mock_post.return_value = _mock_response(409, text="still aborted")

        resp = _insert_with_retry(
            {"Authorization": "Bearer tok"}, "PL1", "vid1",
            max_retries=2, initial_backoff=1.0,
        )

        assert resp.status_code == 409
        # initial + 2 retries = 3 total calls
        assert mock_post.call_count == 3
        # 2 sleeps: 1.0, 2.0
        assert mock_sleep.call_count == 2

    @patch("song_shake.features.vibing.youtube_sync.time.sleep")
    @patch("song_shake.features.vibing.youtube_sync.requests.post")
    def test_non_retryable_error_no_retry(self, mock_post, mock_sleep):
        """Non-retryable status (e.g., 400) returns immediately without retry."""
        mock_post.return_value = _mock_response(400, text="bad request")

        resp = _insert_with_retry(
            {"Authorization": "Bearer tok"}, "PL1", "vid1",
            max_retries=3,
        )

        assert resp.status_code == 400
        assert mock_post.call_count == 1
        mock_sleep.assert_not_called()


# ---------------------------------------------------------------------------
# create_youtube_playlist
# ---------------------------------------------------------------------------


class TestCreateYoutubePlaylist:
    """Tests for the full playlist creation flow."""

    @patch("song_shake.features.vibing.youtube_sync.time.sleep")
    @patch("song_shake.features.vibing.youtube_sync._insert_with_retry")
    @patch("song_shake.features.vibing.youtube_sync.requests.post")
    def test_all_inserts_succeed(self, mock_post, mock_insert, mock_sleep):
        """All tracks inserted successfully."""
        mock_post.return_value = _mock_response(200, {"id": "PL123"})
        mock_insert.return_value = _mock_response(200)

        result = create_youtube_playlist("token", "My Playlist", ["v1", "v2", "v3"])

        assert isinstance(result, SyncResult)
        assert result.playlist_id == "PL123"
        assert result.inserted == 3
        assert result.failed_video_ids == []

    @patch("song_shake.features.vibing.youtube_sync.time.sleep")
    @patch("song_shake.features.vibing.youtube_sync._insert_with_retry")
    @patch("song_shake.features.vibing.youtube_sync.requests.post")
    def test_some_inserts_fail(self, mock_post, mock_insert, mock_sleep):
        """Tracks that fail after retries appear in failed_video_ids."""
        mock_post.return_value = _mock_response(200, {"id": "PL123"})
        mock_insert.side_effect = [
            _mock_response(200),
            _mock_response(409, text="aborted"),
            _mock_response(200),
        ]

        result = create_youtube_playlist("token", "Mix", ["v1", "v2", "v3"])

        assert result.inserted == 2
        assert result.failed_video_ids == ["v2"]

    @patch("song_shake.features.vibing.youtube_sync.requests.post")
    def test_playlist_creation_fails(self, mock_post):
        """RuntimeError raised when playlist creation itself fails."""
        mock_post.return_value = _mock_response(403, text="quota exceeded")

        with pytest.raises(RuntimeError, match="playlist creation failed"):
            create_youtube_playlist("token", "Title", ["v1"])

    @patch("song_shake.features.vibing.youtube_sync.time.sleep")
    @patch("song_shake.features.vibing.youtube_sync._insert_with_retry")
    @patch("song_shake.features.vibing.youtube_sync.requests.post")
    def test_quota_callback_called(self, mock_post, mock_insert, mock_sleep):
        """on_quota_used is called for playlist creation and each successful insert."""
        mock_post.return_value = _mock_response(200, {"id": "PL1"})
        mock_insert.return_value = _mock_response(200)
        callback = MagicMock()

        create_youtube_playlist("token", "T", ["v1", "v2"], on_quota_used=callback)

        # 1 for playlist + 2 for items = 3 calls
        assert callback.call_count == 3
        callback.assert_called_with(50)


# ---------------------------------------------------------------------------
# _fetch_existing_video_ids
# ---------------------------------------------------------------------------


class TestFetchExistingVideoIds:
    """Tests for fetching existing playlist items from YouTube."""

    @patch("song_shake.features.vibing.youtube_sync.requests.get")
    def test_single_page(self, mock_get):
        """Fetches all video IDs from a single page."""
        mock_get.return_value = _mock_response(200, {
            "items": [
                {"snippet": {"resourceId": {"videoId": "v1"}}},
                {"snippet": {"resourceId": {"videoId": "v2"}}},
            ],
        })

        result = _fetch_existing_video_ids({"Authorization": "Bearer tok"}, "PL1")

        assert result == {"v1", "v2"}
        assert mock_get.call_count == 1

    @patch("song_shake.features.vibing.youtube_sync.requests.get")
    def test_multiple_pages(self, mock_get):
        """Paginates through multiple pages to collect all video IDs."""
        mock_get.side_effect = [
            _mock_response(200, {
                "items": [{"snippet": {"resourceId": {"videoId": "v1"}}}],
                "nextPageToken": "abc",
            }),
            _mock_response(200, {
                "items": [{"snippet": {"resourceId": {"videoId": "v2"}}}],
            }),
        ]

        result = _fetch_existing_video_ids({"Authorization": "Bearer tok"}, "PL1")

        assert result == {"v1", "v2"}
        assert mock_get.call_count == 2

    @patch("song_shake.features.vibing.youtube_sync.requests.get")
    def test_api_failure_raises(self, mock_get):
        """RuntimeError raised when the API returns an error."""
        mock_get.return_value = _mock_response(403, text="forbidden")

        with pytest.raises(RuntimeError, match="Failed to fetch"):
            _fetch_existing_video_ids({"Authorization": "Bearer tok"}, "PL1")


# ---------------------------------------------------------------------------
# complete_youtube_playlist
# ---------------------------------------------------------------------------


class TestCompleteYoutubePlaylist:
    """Tests for inserting only missing tracks into an existing playlist."""

    @patch("song_shake.features.vibing.youtube_sync.time.sleep")
    @patch("song_shake.features.vibing.youtube_sync._insert_with_retry")
    @patch("song_shake.features.vibing.youtube_sync._fetch_existing_video_ids")
    def test_inserts_only_missing(self, mock_fetch, mock_insert, mock_sleep):
        """Only tracks not already in the playlist are inserted."""
        mock_fetch.return_value = {"v1", "v3"}
        mock_insert.return_value = _mock_response(200)

        result = complete_youtube_playlist(
            "token", "PL1", ["v1", "v2", "v3", "v4"],
        )

        assert result.inserted == 2
        assert result.failed_video_ids == []
        # v2 and v4 were missing
        assert mock_insert.call_count == 2

    @patch("song_shake.features.vibing.youtube_sync.time.sleep")
    @patch("song_shake.features.vibing.youtube_sync._insert_with_retry")
    @patch("song_shake.features.vibing.youtube_sync._fetch_existing_video_ids")
    def test_nothing_missing(self, mock_fetch, mock_insert, mock_sleep):
        """Returns immediately if all tracks already present."""
        mock_fetch.return_value = {"v1", "v2", "v3"}

        result = complete_youtube_playlist("token", "PL1", ["v1", "v2", "v3"])

        assert result.inserted == 0
        assert result.failed_video_ids == []
        mock_insert.assert_not_called()

    @patch("song_shake.features.vibing.youtube_sync.time.sleep")
    @patch("song_shake.features.vibing.youtube_sync._insert_with_retry")
    @patch("song_shake.features.vibing.youtube_sync._fetch_existing_video_ids")
    def test_partial_failure(self, mock_fetch, mock_insert, mock_sleep):
        """Some missing tracks fail to insert, reported in failed_video_ids."""
        mock_fetch.return_value = {"v1"}
        mock_insert.side_effect = [
            _mock_response(200),
            _mock_response(409, text="still aborted"),
        ]

        result = complete_youtube_playlist("token", "PL1", ["v1", "v2", "v3"])

        assert result.inserted == 1
        assert result.failed_video_ids == ["v3"]

    @patch("song_shake.features.vibing.youtube_sync.time.sleep")
    @patch("song_shake.features.vibing.youtube_sync._insert_with_retry")
    @patch("song_shake.features.vibing.youtube_sync._fetch_existing_video_ids")
    def test_quota_callback_only_on_success(self, mock_fetch, mock_insert, mock_sleep):
        """on_quota_used is called only for successful inserts."""
        mock_fetch.return_value = set()
        mock_insert.side_effect = [
            _mock_response(200),
            _mock_response(409),
        ]
        callback = MagicMock()

        complete_youtube_playlist("token", "PL1", ["v1", "v2"], on_quota_used=callback)

        callback.assert_called_once_with(50)
