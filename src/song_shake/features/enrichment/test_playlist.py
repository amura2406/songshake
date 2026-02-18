"""Unit tests for enrichment playlist functions."""

from unittest.mock import MagicMock, patch

import pytest


# --- list_playlists tests ---


class TestListPlaylists:
    """Tests for list_playlists()."""

    @patch("song_shake.features.enrichment.playlist.get_ytmusic")
    def test_list_playlists_success(self, mock_get_yt, capsys):
        """Should display playlists in a Rich table."""
        yt = MagicMock()
        yt.get_library_playlists.return_value = [
            {"playlistId": "PL1", "title": "My Playlist", "count": 10},
            {"playlistId": "PL2", "title": "Another", "count": None},
        ]
        mock_get_yt.return_value = yt

        from song_shake.features.enrichment.playlist import list_playlists

        list_playlists()

        yt.get_library_playlists.assert_called_once_with(limit=50)

    @patch("song_shake.features.enrichment.playlist.get_ytmusic")
    def test_list_playlists_handles_error(self, mock_get_yt, capsys):
        """Should print error message when fetching fails."""
        mock_get_yt.side_effect = Exception("Auth failed")

        from song_shake.features.enrichment.playlist import list_playlists

        list_playlists()
        # Should not raise — error is printed to console


# --- get_tracks tests ---


class TestGetTracks:
    """Tests for get_tracks()."""

    @patch("song_shake.features.enrichment.playlist.get_ytmusic")
    def test_returns_tracks_from_playlist(self, mock_get_yt):
        """Should return tracks from YTMusic playlist."""
        yt = MagicMock()
        yt.get_playlist.return_value = {
            "tracks": [
                {"videoId": "v1", "title": "Song 1"},
                {"videoId": "v2", "title": "Song 2"},
            ]
        }
        mock_get_yt.return_value = yt

        from song_shake.features.enrichment.playlist import get_tracks

        tracks = get_tracks("PL_test")

        assert len(tracks) == 2
        assert tracks[0]["videoId"] == "v1"
        yt.get_playlist.assert_called_once_with("PL_test", limit=None)

    @patch("song_shake.features.enrichment.playlist.get_ytmusic")
    def test_falls_back_to_data_api(self, mock_get_yt):
        """Should fall back to Data API when get_playlist fails."""
        yt = MagicMock()
        yt.get_playlist.side_effect = Exception("API error")
        mock_get_yt.return_value = yt

        with patch(
            "song_shake.features.auth.auth.get_data_api_tracks"
        ) as mock_fallback:
            mock_fallback.return_value = [{"videoId": "v3", "title": "Fallback"}]

            from song_shake.features.enrichment.playlist import get_tracks

            tracks = get_tracks("PL_test")

            assert len(tracks) == 1
            mock_fallback.assert_called_once()

    @patch("song_shake.features.enrichment.playlist.get_ytmusic")
    def test_returns_empty_when_both_fail(self, mock_get_yt):
        """Should return empty list when both methods fail."""
        yt = MagicMock()
        yt.get_playlist.side_effect = Exception("Primary fail")
        mock_get_yt.return_value = yt

        with patch(
            "song_shake.features.auth.auth.get_data_api_tracks"
        ) as mock_fallback:
            mock_fallback.side_effect = Exception("Fallback fail")

            from song_shake.features.enrichment.playlist import get_tracks

            tracks = get_tracks("PL_test")

            assert tracks == []


# --- get_playlist_title tests ---


class TestGetPlaylistTitle:
    """Tests for get_playlist_title()."""

    @patch("song_shake.features.enrichment.playlist.get_ytmusic")
    def test_returns_playlist_title(self, mock_get_yt):
        """Should return the playlist title."""
        yt = MagicMock()
        yt.get_playlist.return_value = {"title": "My Great Playlist"}
        mock_get_yt.return_value = yt

        from song_shake.features.enrichment.playlist import get_playlist_title

        title = get_playlist_title("PL_test")

        assert title == "My Great Playlist"
        yt.get_playlist.assert_called_once_with("PL_test", limit=1)

    @patch("song_shake.features.enrichment.playlist.get_ytmusic")
    def test_returns_unknown_on_error(self, mock_get_yt):
        """Should return 'Unknown Playlist' when fetch fails."""
        yt = MagicMock()
        yt.get_playlist.side_effect = Exception("Not found")
        mock_get_yt.return_value = yt

        from song_shake.features.enrichment.playlist import get_playlist_title

        title = get_playlist_title("PL_bad")

        assert title == "Unknown Playlist"
