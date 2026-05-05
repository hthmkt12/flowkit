"""Tests for worker retry logic — error classification and backoff scheduling."""
import pytest
from agent.worker.processor import _classify_error, _next_retry_delay_s


class TestClassifyError:
    """Test error classification for retry decisions."""

    @pytest.mark.parametrize("msg,expected", [
        ("invalid api key", "NON_RETRYABLE"),
        ("Unauthorized access to resource", "NON_RETRYABLE"),
        ("403 Forbidden", "NON_RETRYABLE"),
        ("User not logged in", "NON_RETRYABLE"),
        ("Unsupported media type", "NON_RETRYABLE"),
        ("Unknown task type: NOOP", "NON_RETRYABLE"),
        ("Validation error: content is required", "NON_RETRYABLE"),
    ])
    def test_non_retryable_errors(self, msg, expected):
        assert _classify_error(msg) == expected

    @pytest.mark.parametrize("msg,expected", [
        ("Connection timeout", "RETRYABLE"),
        ("Network error", "RETRYABLE"),
        ("Element not found on page", "RETRYABLE"),
        ("No Facebook tab open", "RETRYABLE"),
        ("Script execution failed", "RETRYABLE"),
        ("", "RETRYABLE"),
        (None, "RETRYABLE"),
    ])
    def test_retryable_errors(self, msg, expected):
        assert _classify_error(msg) == expected

    def test_case_insensitive(self):
        assert _classify_error("INVALID API KEY") == "NON_RETRYABLE"
        assert _classify_error("Forbidden") == "NON_RETRYABLE"


class TestNextRetryDelay:
    """Test exponential backoff calculation."""

    def test_first_retry(self):
        delay = _next_retry_delay_s(1)
        assert delay >= 2  # base^1 = 2, + small jitter
        assert delay <= 5  # 2 + max jitter(2)

    def test_second_retry(self):
        delay = _next_retry_delay_s(2)
        assert delay >= 4  # base^2 = 4
        assert delay <= 7  # 4 + max jitter(2)

    def test_increasing_delays(self):
        d1 = _next_retry_delay_s(1)
        d2 = _next_retry_delay_s(2)
        d3 = _next_retry_delay_s(3)
        # Exponential: each should generally be larger
        # (jitter can cause overlap, but base grows)
        assert d2 >= d1  # 4 >= 2
        assert d3 >= d2  # 8 >= 4

    def test_cap_at_120(self):
        delay = _next_retry_delay_s(10)
        # base^10 = 1024, capped at 120 + jitter(max 2)
        assert delay <= 123

    def test_zero_retry_uses_min_one(self):
        delay = _next_retry_delay_s(0)
        # max(0,1) = 1, base^1 = 2
        assert delay >= 2

    def test_deterministic_jitter(self):
        """Same retry_count always produces the same delay."""
        assert _next_retry_delay_s(3) == _next_retry_delay_s(3)
        assert _next_retry_delay_s(5) == _next_retry_delay_s(5)
