"""Tests for config helpers."""
import pytest
from agent.config import _is_truthy


class TestIsTruthy:
    @pytest.mark.parametrize("val,expected", [
        ("1", True),
        ("true", True),
        ("True", True),
        ("TRUE", True),
        ("yes", True),
        ("Yes", True),
        ("on", True),
        ("ON", True),
        ("  true  ", True),  # Whitespace trimmed
    ])
    def test_truthy_values(self, val, expected):
        assert _is_truthy(val) == expected

    @pytest.mark.parametrize("val,expected", [
        ("0", False),
        ("false", False),
        ("False", False),
        ("no", False),
        ("off", False),
        ("", False),
        ("random", False),
    ])
    def test_falsy_values(self, val, expected):
        assert _is_truthy(val) == expected

    def test_none_default_false(self):
        assert _is_truthy(None) is False

    def test_none_default_true(self):
        assert _is_truthy(None, default=True) is True
