"""Integration tests for FirestoreTokenAdapter against Firebase emulator.

Run with:
    firebase emulators:start --only firestore &
    FIRESTORE_EMULATOR_HOST=localhost:8081 uv run pytest src/song_shake/platform/test_firestore_token_integration.py -v
"""


class TestFirestoreTokenAdapter:
    """Integration tests for FirestoreTokenAdapter (TokenStoragePort)."""

    def test_save_and_get_tokens(self, token_adapter):
        """Should persist tokens and retrieve them by user ID."""
        tokens = {
            "access_token": "ya29.fake",
            "refresh_token": "1//fake_refresh",
            "expires_at": 1700000000,
        }
        token_adapter.save_google_tokens("user_1", tokens)

        result = token_adapter.get_google_tokens("user_1")
        assert result is not None
        assert result["access_token"] == "ya29.fake"
        assert result["refresh_token"] == "1//fake_refresh"
        assert result["user_id"] == "user_1"

    def test_get_tokens_returns_none_for_missing_user(self, token_adapter):
        """Should return None for a user with no stored tokens."""
        assert token_adapter.get_google_tokens("nonexistent") is None

    def test_save_tokens_upserts(self, token_adapter):
        """Should overwrite existing tokens for the same user."""
        token_adapter.save_google_tokens("user_1", {
            "access_token": "old_token", "refresh_token": "old_refresh",
        })
        token_adapter.save_google_tokens("user_1", {
            "access_token": "new_token", "refresh_token": "new_refresh",
        })

        result = token_adapter.get_google_tokens("user_1")
        assert result["access_token"] == "new_token"
        assert result["refresh_token"] == "new_refresh"

    def test_delete_tokens(self, token_adapter):
        """Should remove tokens for a user."""
        token_adapter.save_google_tokens("user_1", {"access_token": "tok"})
        token_adapter.delete_google_tokens("user_1")

        assert token_adapter.get_google_tokens("user_1") is None

    def test_delete_nonexistent_is_safe(self, token_adapter):
        """Deleting tokens for a nonexistent user should not raise."""
        token_adapter.delete_google_tokens("nonexistent")

    def test_tokens_isolated_by_user(self, token_adapter):
        """Different users' tokens should be independent."""
        token_adapter.save_google_tokens("alice", {"access_token": "alice_tok"})
        token_adapter.save_google_tokens("bob", {"access_token": "bob_tok"})

        alice = token_adapter.get_google_tokens("alice")
        bob = token_adapter.get_google_tokens("bob")

        assert alice["access_token"] == "alice_tok"
        assert bob["access_token"] == "bob_tok"

        token_adapter.delete_google_tokens("alice")
        assert token_adapter.get_google_tokens("alice") is None
        assert token_adapter.get_google_tokens("bob") is not None
