# tests/test_transform.py

"""
Unit tests for the transform module.
Run with: pytest tests/ -v
"""

import datetime
import pytest
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, Polygon

# Patch config imports before importing transform
import sys
import types

# Minimal config stub so transform.py can be imported without a .env
_cfg = types.ModuleType("scripts.config")
_cfg.GEOGRAPHIC_CRS         = "EPSG:4326"
_cfg.METRIC_CRS             = "EPSG:3857"
_cfg.ZONE_BUFFER_METERS     = 500
_cfg.STOP_DURATION_THRESHOLD_MIN = 10
_cfg.LONG_STOP_THRESHOLD_MIN     = 60
_cfg.AFTER_HOURS_START      = 18
_cfg.AFTER_HOURS_END        = 6
_cfg.WEEKEND_DAYS           = [5, 6]
_cfg.IDLE_THRESHOLD_TICKS   = 600
_cfg.FAR_FROM_ZONE_THRESHOLD_KM = 5.0

_log = types.ModuleType("scripts.logger")
import logging
_log.logger = logging.getLogger("test")

sys.modules.setdefault("scripts.config", _cfg)
sys.modules.setdefault("scripts.logger", _log)

from scripts.transform import (
    _parse_duration_minutes,
    _is_after_hours,
    _is_weekend,
    create_zones_gdf,
    create_trips_gdf,
    engineer_features,
    build_device_summary,
    build_zone_summary,
)


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

class TestParseDuration:
    def test_none_returns_zero(self):
        assert _parse_duration_minutes(None) == 0.0

    def test_numeric(self):
        assert _parse_duration_minutes(45.5) == 45.5

    def test_time_object(self):
        t = datetime.time(1, 30, 0)
        assert _parse_duration_minutes(t) == 90.0

    def test_string_number(self):
        assert _parse_duration_minutes("20") == 20.0

    def test_bad_string(self):
        assert _parse_duration_minutes("bad") == 0.0


class TestAfterHours:
    def test_midnight_is_after_hours(self):
        dt = pd.Timestamp("2024-01-15 00:00:00", tz="UTC")
        assert _is_after_hours(dt) is True

    def test_midday_is_not_after_hours(self):
        dt = pd.Timestamp("2024-01-15 12:00:00", tz="UTC")
        assert _is_after_hours(dt) is False

    def test_evening_is_after_hours(self):
        dt = pd.Timestamp("2024-01-15 19:00:00", tz="UTC")
        assert _is_after_hours(dt) is True

    def test_none_returns_false(self):
        assert _is_after_hours(None) is False


class TestWeekend:
    def test_saturday_is_weekend(self):
        dt = pd.Timestamp("2024-01-13", tz="UTC")  # Saturday
        assert _is_weekend(dt) is True

    def test_monday_is_not_weekend(self):
        dt = pd.Timestamp("2024-01-15", tz="UTC")  # Monday
        assert _is_weekend(dt) is False

    def test_none_returns_false(self):
        assert _is_weekend(None) is False


# ─────────────────────────────────────────────
# GeoDataFrame builders
# ─────────────────────────────────────────────

def _make_zone_df():
    return pd.DataFrame([{
        "ZoneID":   "z1",
        "ZoneName": "Depot A",
        "ZoneType": "Customer",
        "Points":   [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0), (0.0, 0.0)],
        "Comment":  "",
        "ActiveFrom": None,
        "ActiveTo":   None,
    }])


def _make_trip_df():
    return pd.DataFrame([{
        "TripID":         "t1",
        "DeviceID":       "d1",
        "DeviceName":     "Truck 01",
        "LicensePlate":   "ABC123",
        "VehicleType":    "",
        "DeviceComment":  "",
        "StartTime":      pd.Timestamp("2024-01-15 08:00:00", tz="UTC"),
        "StopTime":       pd.Timestamp("2024-01-15 08:45:00", tz="UTC"),
        "TripDurationMin": 45.0,
        "Latitude":       0.5,
        "Longitude":      0.5,
        "Distance":       10.0,
        "DurationStop":   15,
        "IdlingTicks":    100,
        "WorkDistance":   8.0,
        "AfterHoursDistance": 0.0,
        "EntityStatus":   "Active",
    }])


class TestCreateZonesGdf:
    def test_basic(self):
        gdf = create_zones_gdf(_make_zone_df())
        assert len(gdf) == 1
        assert gdf.crs.to_epsg() == 4326

    def test_empty_input(self):
        gdf = create_zones_gdf(pd.DataFrame(columns=["ZoneID", "ZoneName", "Points"]))
        assert gdf.empty

    def test_too_few_points_skipped(self):
        df = _make_zone_df()
        df.at[0, "Points"] = [(0.0, 0.0), (1.0, 0.0)]  # only 2 points
        gdf = create_zones_gdf(df)
        assert gdf.empty


class TestCreateTripsGdf:
    def test_basic(self):
        gdf = create_trips_gdf(_make_trip_df())
        assert len(gdf) == 1
        assert gdf.crs.to_epsg() == 4326

    def test_missing_lat_lon_dropped(self):
        df = _make_trip_df()
        df.at[0, "Latitude"] = None
        gdf = create_trips_gdf(df)
        assert gdf.empty

    def test_missing_columns(self):
        df = _make_trip_df().drop(columns=["Latitude"])
        gdf = create_trips_gdf(df)
        assert gdf.empty


# ─────────────────────────────────────────────
# Feature engineering
# ─────────────────────────────────────────────

class TestEngineerFeatures:
    def setup_method(self):
        trips  = create_trips_gdf(_make_trip_df())
        zones  = create_zones_gdf(_make_zone_df())
        # Manually add spatial columns (bypass full spatial join for unit test)
        trips["NearestZone"]   = "Depot A"
        trips["DistanceMeters"] = 0.0
        trips["DistanceKm"]    = 0.0
        trips["InsideZone"]    = True
        trips["ZoneLatitude"]  = 0.5
        trips["ZoneLongitude"] = 0.5
        self.gdf = engineer_features(trips)

    def test_stop_duration_min(self):
        assert self.gdf["StopDurationMin"].iloc[0] == 15.0

    def test_stop_over_10min(self):
        assert self.gdf["StopOver10Min"].iloc[0] is True

    def test_after_hours_false(self):
        # StopTime = 08:45 UTC — not after hours
        assert self.gdf["AfterHoursStop"].iloc[0] is False

    def test_weekend_false(self):
        # 2024-01-15 = Monday
        assert self.gdf["WeekendStop"].iloc[0] is False

    def test_far_from_zone_false(self):
        assert self.gdf["FarFromZone"].iloc[0] is False


# ─────────────────────────────────────────────
# Summary builders
# ─────────────────────────────────────────────

class TestSummaries:
    def setup_method(self):
        trips = create_trips_gdf(_make_trip_df())
        trips["NearestZone"]     = "Depot A"
        trips["DistanceMeters"]  = 0.0
        trips["DistanceKm"]      = 0.0
        trips["InsideZone"]      = True
        trips["ZoneLatitude"]    = 0.5
        trips["ZoneLongitude"]   = 0.5
        self.gdf = engineer_features(trips)

    def test_device_summary_has_one_row(self):
        ds = build_device_summary(self.gdf)
        assert len(ds) == 1
        assert ds["TotalTrips"].iloc[0] == 1

    def test_zone_summary_has_one_row(self):
        zs = build_zone_summary(self.gdf)
        assert len(zs) == 1
        assert zs["ZoneName"].iloc[0] == "Depot A"

    def test_empty_gdf(self):
        empty = gpd.GeoDataFrame()
        assert build_device_summary(empty).empty
        assert build_zone_summary(empty).empty
