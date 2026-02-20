"""TinyDB adapter wrapping auth/token_store functions behind TokenStoragePort."""

from song_shake.features.auth import token_store


class TinyDBTokenAdapter:
    """Wraps song_shake.features.auth.token_store behind TokenStoragePort Protocol."""

    def save_google_tokens(self, user_id: str, tokens: dict) -> None:
        token_store.save_google_tokens(user_id, tokens)

    def get_google_tokens(self, user_id: str) -> dict | None:
        return token_store.get_google_tokens(user_id)

    def delete_google_tokens(self, user_id: str) -> None:
        token_store.delete_google_tokens(user_id)
