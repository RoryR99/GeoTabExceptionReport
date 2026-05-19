"""
Unit tests for trip window resolution in extract.py.
"""

from datetime import datetime, timezone
import logging
import sys
import types

import pytest


_cfg = types.ModuleType("scripts.config")
_cfg.RAW_TRIPS_CSV = "output/raw_trips.csv"

_log = types.ModuleType("scripts.logger")
_log.logger = logging.getLogger("test")

_client = types.ModuleType("scripts.geotab_client")
_client.api_get_with_retry = lambda *args, **kwargs: []

sys.modules.setdefault("scripts.config", _cfg)
sys.modules.setdefault("scripts.logger", _log)
sys.modules.setdefault("scripts.geotab_client", _client)

from scripts.extract import resolve_trip_window


def test_days_back_uses_relative_window():
    now = datetime(2026, 5, 12, 15, 0, tzinfo=timezone.utc)

    start, end = resolve_trip_window(days_back=30, now=now)

    assert end == now
    assert start == datetime(2026, 4, 12, 15, 0, tzinfo=timezone.utc)


def test_explicit_date_frame_uses_full_day_bounds():
    start, end = resolve_trip_window(
        start_date="2026-05-01",
        end_date="2026-05-12",
    )

    assert start == datetime(2026, 5, 1, 0, 0, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 5, 12, 23, 59, 59, 999999, tzinfo=timezone.utc)


def test_explicit_datetime_preserves_exact_timestamp():
    start, end = resolve_trip_window(
        start_date="2026-05-01T08:30:00+00:00",
        end_date="2026-05-12T17:45:00+00:00",
    )

    assert start == datetime(2026, 5, 1, 8, 30, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 5, 12, 17, 45, 0, tzinfo=timezone.utc)


def test_rejects_partial_explicit_date_frame():
    with pytest.raises(ValueError, match="Both start_date and end_date"):
        resolve_trip_window(start_date="2026-05-01")


def test_rejects_inverted_date_frame():
    with pytest.raises(ValueError, match="start_date must be earlier"):
        resolve_trip_window(
            start_date="2026-05-12",
            end_date="2026-05-01",
        )
