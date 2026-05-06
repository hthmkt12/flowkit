"""Tests for timezone-safe UTC timestamp helpers."""

from datetime import datetime

from agent.utils.time import utc_from_timestamp_iso, utc_now, utc_now_iso, utc_now_ms


def test_utc_now_preserves_naive_datetime_contract():
    value = utc_now()

    assert value.tzinfo is None


def test_utc_now_iso_preserves_naive_iso_storage_format():
    value = utc_now_iso()

    parsed = datetime.fromisoformat(value)
    assert parsed.tzinfo is None
    assert "+00:00" not in value
    assert value.endswith("Z") is False


def test_utc_now_ms_returns_epoch_milliseconds():
    value = utc_now_ms()

    assert isinstance(value, int)
    assert value > 1_700_000_000_000


def test_utc_from_timestamp_iso_preserves_naive_iso_storage_format():
    value = utc_from_timestamp_iso(1_700_000_000)

    assert value == "2023-11-14T22:13:20"
