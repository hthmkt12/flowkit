"""Tests for config helpers."""
import pytest
from agent.config import _csv, _is_truthy


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


class TestCsv:
    def test_none_returns_default(self):
        assert _csv(None, ["http://127.0.0.1:5173"]) == ["http://127.0.0.1:5173"]

    def test_csv_trims_and_drops_empty_items(self):
        assert _csv(" http://a.test, ,http://b.test ", []) == ["http://a.test", "http://b.test"]
