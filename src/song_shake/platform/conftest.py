"""Integration test fixtures for Firebase emulator.

Requires:
  1. firebase-admin installed:  uv sync --extra firebase
  2. Firebase emulator running: firebase emulators:start --only firestore

When either requirement is missing, all tests in this directory are skipped.
"""

import os

import pytest

firebase_admin = pytest.importorskip("firebase_admin", reason="firebase-admin not installed")


def _emulator_running() -> bool:
    """Check if the Firestore emulator is reachable."""
    host = os.environ.get("FIRESTORE_EMULATOR_HOST", "localhost:8081")
    try:
        import urllib.request
        urllib.request.urlopen(f"http://{host}", timeout=2)
        return True
    except Exception:
        return False


if not _emulator_running():
    pytest.skip(
        "Firebase emulator not running (start with: firebase emulators:start --only firestore)",
        allow_module_level=True,
    )


from song_shake.platform.firestore_adapter import (  # noqa: E402
    FirestoreJobsAdapter,
    FirestoreSongsAdapter,
    FirestoreTokenAdapter,
    _firestore_client,
)


@pytest.fixture(autouse=True)
def _set_emulator_env(monkeypatch):
    """Ensure FIRESTORE_EMULATOR_HOST is set for all integration tests."""
    host = os.environ.get("FIRESTORE_EMULATOR_HOST", "localhost:8081")
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", host)


@pytest.fixture(autouse=True)
def _clear_firebase_app():
    """Reset firebase-admin between tests to use emulator config."""
    _firestore_client.cache_clear()
    yield
    _firestore_client.cache_clear()
    try:
        for app_name in list(firebase_admin._apps.keys()):
            firebase_admin.delete_app(firebase_admin._apps[app_name])
    except Exception:
        pass


@pytest.fixture
def songs_adapter():
    """Return a FirestoreSongsAdapter pointed at the emulator."""
    adapter = FirestoreSongsAdapter()
    yield adapter
    adapter.wipe_db()


@pytest.fixture
def jobs_adapter():
    """Return a FirestoreJobsAdapter pointed at the emulator."""
    adapter = FirestoreJobsAdapter()
    yield adapter
    db = adapter._db
    for coll_name in ["jobs", "ai_usage"]:
        for doc in db.collection(coll_name).stream():
            doc.reference.delete()


@pytest.fixture
def token_adapter():
    """Return a FirestoreTokenAdapter pointed at the emulator."""
    adapter = FirestoreTokenAdapter()
    yield adapter
    for doc in adapter._db.collection("google_tokens").stream():
        doc.reference.delete()
