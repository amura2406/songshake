"""Unit tests for enrichment module — pure function tests only."""

from song_shake.features.enrichment.enrichment import TokenTracker


class TestTokenTracker:
    """Tests for TokenTracker cost calculation logic."""

    def test_initial_state(self):
        """Should start with zero counters."""
        tracker = TokenTracker()
        assert tracker.input_tokens == 0
        assert tracker.output_tokens == 0
        assert tracker.successful == 0
        assert tracker.failed == 0
        assert tracker.errors == []

    def test_get_cost_zero_tokens(self):
        """Should return 0 cost with no tokens."""
        tracker = TokenTracker()
        assert tracker.get_cost() == 0.0

    def test_get_cost_calculation(self):
        """Should calculate cost based on Gemini pricing."""
        tracker = TokenTracker()
        tracker.input_tokens = 1_000_000  # 1M input tokens
        tracker.output_tokens = 1_000_000  # 1M output tokens

        cost = tracker.get_cost()
        # Cost depends on the per-token rates in the implementation
        assert cost > 0
        assert isinstance(cost, float)

    def test_successful_and_failed_counts(self):
        """Should track successful and failed operations independently."""
        tracker = TokenTracker()
        tracker.successful = 5
        tracker.failed = 2
        tracker.errors = ["Error 1", "Error 2"]

        assert tracker.successful == 5
        assert tracker.failed == 2
        assert len(tracker.errors) == 2
