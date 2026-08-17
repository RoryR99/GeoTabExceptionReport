# scripts/transform.py

import datetime

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon

from scripts.logger import logger
from scripts.config import (
    GEOGRAPHIC_CRS, METRIC_CRS,
    ZONE_BUFFER_METERS,
    STOP_DURATION_THRESHOLD_MIN, LONG_STOP_THRESHOLD_MIN,
    AFTER_HOURS_START, AFTER_HOURS_END, WEEKEND_DAYS,
    IDLE_THRESHOLD_TICKS, FAR_FROM_ZONE_THRESHOLD_KM,
)


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _parse_duration_minutes(value) -> float:
    """Convert a duration value (datetime.time or numeric) to minutes."""
    if value is None:
        return 0.0
    try:
        if isinstance(value, datetime.time):
            return value.hour * 60 + value.minute + value.second / 60
        return float(value)
    except Exception:
        return 0.0


def _is_after_hours(dt) -> bool:
    """Return True if the datetime falls outside normal business hours."""
    if dt is None:
        return False
    try:
        hour = dt.hour if hasattr(dt, "hour") else pd.Timestamp(dt).hour
        return hour >= AFTER_HOURS_START or hour < AFTER_HOURS_END
    except Exception:
        return False


def _is_weekend(dt) -> bool:
    """Return True if the datetime falls on a weekend."""
    if dt is None:
        return False
    try:
        weekday = dt.weekday() if hasattr(dt, "weekday") else pd.Timestamp(dt).weekday()
        return weekday in WEEKEND_DAYS
    except Exception:
        return False


# ─────────────────────────────────────────────
# GeoDataFrame builders
# ─────────────────────────────────────────────

def create_zones_gdf(df_zones: pd.DataFrame) -> gpd.GeoDataFrame:
    """
    Convert a zones DataFrame into a GeoDataFrame with Polygon geometry.

    Invalid polygons are auto-repaired with buffer(0). Rows with fewer
    than 3 coordinate points are silently dropped.

    Args:
        df_zones: DataFrame produced by extract.fetch_zones().

    Returns:
        GeoDataFrame in EPSG:4326.
    """
    polygons   = []
    valid_rows = []

    for _, row in df_zones.iterrows():
        points = row.get("Points", [])
        if not points or len(points) < 3:
            continue
        try:
            poly = Polygon(points)
            if not poly.is_valid:
                poly = poly.buffer(0)
            polygons.append(poly)
            valid_rows.append(row)
        except Exception as e:
            logger.warning(f"Skipping zone '{row.get('ZoneID')}': geometry error — {e}")

    if not valid_rows:
        logger.warning("No valid zones could be built.")
        return gpd.GeoDataFrame(columns=df_zones.columns, geometry=[], crs=GEOGRAPHIC_CRS)

    gdf = gpd.GeoDataFrame(valid_rows, geometry=polygons, crs=GEOGRAPHIC_CRS)
    logger.info(f"Zones GeoDataFrame: {len(gdf)} zones.")
    return gdf


def create_trips_gdf(df_trips: pd.DataFrame) -> gpd.GeoDataFrame:
    """
    Convert a trips DataFrame into a GeoDataFrame (Point geometry at stop location).

    Rows missing Latitude or Longitude are dropped with a warning.

    Args:
        df_trips: DataFrame produced by extract.fetch_trips().

    Returns:
        GeoDataFrame in EPSG:4326.
    """
    if "Latitude" not in df_trips.columns or "Longitude" not in df_trips.columns:
        logger.warning("Trips DataFrame is missing Latitude/Longitude columns.")
        return gpd.GeoDataFrame(columns=df_trips.columns, geometry=[], crs=GEOGRAPHIC_CRS)

    df_valid = df_trips.dropna(subset=["Latitude", "Longitude"]).copy()
    dropped  = len(df_trips) - len(df_valid)
    if dropped:
        logger.warning(f"{dropped} trips dropped due to missing coordinates.")

    logger.info(f"Trips with valid coordinates: {len(df_valid)} / {len(df_trips)}.")
    gdf = gpd.GeoDataFrame(
        df_valid,
        geometry=gpd.points_from_xy(df_valid["Longitude"], df_valid["Latitude"]),
        crs=GEOGRAPHIC_CRS,
    )
    return gdf


# ─────────────────────────────────────────────
# Spatial join (vectorised)
# ─────────────────────────────────────────────

def spatial_join_nearest(
    trips_gdf: gpd.GeoDataFrame,
    zones_gdf: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """
    For each trip find the nearest zone using GeoPandas sjoin_nearest
    (spatial-index backed — vastly faster than a manual loop).

    Adds columns:
        NearestZone, ZoneType, DistanceMeters, DistanceKm,
        InsideZone, ZoneLatitude, ZoneLongitude.

    Args:
        trips_gdf: GeoDataFrame of trip stop points (EPSG:4326).
        zones_gdf: GeoDataFrame of zone polygons (EPSG:4326).

    Returns:
        trips_gdf enriched with spatial columns.
    """
    if trips_gdf.empty:
        logger.warning("No trips to spatially join.")
        return trips_gdf

    trips_m = trips_gdf.to_crs(METRIC_CRS).copy()
    zones_m = zones_gdf.to_crs(METRIC_CRS).copy()

    # Precompute zone centroids in geographic CRS once
    zones_centroids = zones_gdf.copy()
    zones_centroids["_centroid"] = zones_gdf.geometry.to_crs(METRIC_CRS).centroid.to_crs(GEOGRAPHIC_CRS)
    zones_centroids["ZoneLatitude"]  = zones_centroids["_centroid"].apply(lambda g: g.y)
    zones_centroids["ZoneLongitude"] = zones_centroids["_centroid"].apply(lambda g: g.x)
    zones_centroids = zones_centroids[["ZoneID", "ZoneName", "ZoneType", "ZoneLatitude", "ZoneLongitude"]]

    # Vectorised nearest join using R-tree spatial index
    join_cols = zones_m[["ZoneID", "ZoneName", "ZoneType", "geometry"]].copy()
    joined = gpd.sjoin_nearest(
        trips_m,
        join_cols.rename(columns={"ZoneID": "_ZoneID", "ZoneName": "NearestZone", "ZoneType": "NearestZoneType"}),
        how="left",
        distance_col="DistanceMeters",
    )

    # Drop sjoin artefact columns
    joined = joined.drop(columns=[c for c in ["index_right"] if c in joined.columns])

    # Round distances
    joined["DistanceMeters"] = joined["DistanceMeters"].round(2)
    joined["DistanceKm"]     = (joined["DistanceMeters"] / 1000).round(3)

    # InsideZone: trip point within buffered zone polygon
    zones_buffered = zones_m.copy()
    zones_buffered["geometry"] = zones_buffered.geometry.buffer(ZONE_BUFFER_METERS)

    inside_flags = []
    for _, trip_row in joined.iterrows():
        pt = trip_row.geometry
        nearest_zone_name = trip_row.get("NearestZone")
        match = zones_buffered[zones_buffered["ZoneName"] == nearest_zone_name]
        if not match.empty and pt is not None and not pt.is_empty:
            inside_flags.append(bool(match.iloc[0].geometry.contains(pt)))
        else:
            inside_flags.append(False)

    joined["InsideZone"] = inside_flags

    # Merge centroid coords back
    joined = joined.merge(
        zones_centroids.rename(columns={"ZoneName": "NearestZone"}),
        on="NearestZone",
        how="left",
        suffixes=("", "_z"),
    )
    # Drop duplicate cols introduced by merge
    joined = joined.drop(columns=[c for c in joined.columns if c.endswith("_z")], errors="ignore")

    # Restore original CRS on geometry
    joined = joined.set_geometry("geometry")
    joined.crs = METRIC_CRS
    joined = joined.to_crs(GEOGRAPHIC_CRS)

    logger.info("Spatial join complete.")
    return joined


# ─────────────────────────────────────────────
# Feature engineering
# ─────────────────────────────────────────────

def engineer_features(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Add business-logic columns to the spatially-joined GeoDataFrame:

    Stop / idle flags:
        StopDurationMin   – stop duration converted to minutes
        StopOver10Min     – stop > STOP_DURATION_THRESHOLD_MIN
        LongStop          – stop > LONG_STOP_THRESHOLD_MIN
        HighIdle          – idling ticks above threshold

    Time-based flags:
        AfterHoursStop    – stop started outside business hours
        WeekendStop       – stop occurred on a weekend
        DayOfWeek         – human-readable day name
        HourOfStop        – integer hour of stop time

    Distance / zone flags:
        FarFromZone       – distance > FAR_FROM_ZONE_THRESHOLD_KM
        OutsideAndStopped – outside zone AND stopped >10 min

    Trip efficiency:
        SpeedKmh          – average speed (Distance / TripDurationMin * 60)
    """
    df = gdf.copy()

    # ── Stop durations ──────────────────────────────────────────────
    df["StopDurationMin"] = df["DurationStop"].apply(_parse_duration_minutes)
    df["StopOver10Min"]   = df["StopDurationMin"] > STOP_DURATION_THRESHOLD_MIN
    df["LongStop"]        = df["StopDurationMin"] > LONG_STOP_THRESHOLD_MIN

    # ── Idling ──────────────────────────────────────────────────────
    df["HighIdle"] = pd.to_numeric(df.get("IdlingTicks", 0), errors="coerce").fillna(0) > IDLE_THRESHOLD_TICKS

    # ── Time-based ──────────────────────────────────────────────────
    stop_times = pd.to_datetime(df["StopTime"], errors="coerce", utc=True)
    df["AfterHoursStop"] = stop_times.apply(lambda t: _is_after_hours(t) if pd.notna(t) else False)
    df["WeekendStop"]    = stop_times.apply(lambda t: _is_weekend(t)     if pd.notna(t) else False)
    df["DayOfWeek"]      = stop_times.dt.day_name().fillna("Unknown")
    df["HourOfStop"]     = stop_times.dt.hour.fillna(-1).astype(int)

    # ── Distance / zone ─────────────────────────────────────────────
    df["FarFromZone"]       = df["DistanceKm"].fillna(0) > FAR_FROM_ZONE_THRESHOLD_KM
    df["OutsideAndStopped"] = (~df["InsideZone"].fillna(False)) & df["StopOver10Min"]

    # ── Trip efficiency ─────────────────────────────────────────────
    dist    = pd.to_numeric(df.get("Distance", None), errors="coerce")
    dur_min = pd.to_numeric(df.get("TripDurationMin", None), errors="coerce")
   
    df["SpeedKmh"] = ((dist / dur_min) * 60).round(2).where(dur_min > 0).replace([float("inf"), float("-inf")], None)

    logger.info("Feature engineering complete.")
    return gpd.GeoDataFrame(df, geometry=df.geometry, crs=GEOGRAPHIC_CRS)


# ─────────────────────────────────────────────
# Device-level summary
# ─────────────────────────────────────────────

def build_device_summary(gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """
    Aggregate trip-level data into per-device KPI summary.

    Returns:
        DataFrame with one row per device containing utilisation metrics.
    """
    if gdf.empty:
        return pd.DataFrame()

    df = pd.DataFrame(gdf.drop(columns="geometry", errors="ignore"))

    group_columns = ["DeviceID", "DeviceName"]
    for optional_column in ["Wave", "Customer"]:
        if optional_column in df.columns:
            group_columns.append(optional_column)

    agg = (
        df.groupby(group_columns)
        .agg(
            TotalTrips          =("TripID",            "count"),
            TotalDistanceKm     =("Distance",          "sum"),
            AvgTripDurationMin  =("TripDurationMin",   "mean"),
            TotalStopMin        =("StopDurationMin",   "sum"),
            LongStops           =("LongStop",          "sum"),
            AfterHoursStops     =("AfterHoursStop",    "sum"),
            WeekendStops        =("WeekendStop",       "sum"),
            OutsideZoneStops    =("OutsideAndStopped", "sum"),
            FarFromZoneTrips    =("FarFromZone",       "sum"),
            HighIdleTrips       =("HighIdle",          "sum"),
            AvgDistanceToZoneKm =("DistanceKm",        "mean"),
        )
        .reset_index()
    )
    agg = agg.round(2)
    logger.info(f"Device summary built for {len(agg)} device(s).")
    return agg


# ─────────────────────────────────────────────
# Zone-level summary
# ─────────────────────────────────────────────

def build_zone_summary(gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """
    Aggregate trip-level data into per-zone visit summary.

    Returns:
        DataFrame with visit counts, avg distances, and anomaly counts per zone.
    """
    if gdf.empty:
        return pd.DataFrame()

    df = pd.DataFrame(gdf.drop(columns="geometry", errors="ignore"))

    agg = (
        df.groupby("NearestZone")
        .agg(
            TotalVisits         =("TripID",            "count"),
            InsideZoneVisits    =("InsideZone",         "sum"),
            OutsideZoneVisits   =("OutsideAndStopped",  "sum"),
            AvgDistanceKm       =("DistanceKm",         "mean"),
            MaxDistanceKm       =("DistanceKm",         "max"),
            LongStops           =("LongStop",           "sum"),
            AfterHoursVisits    =("AfterHoursStop",     "sum"),
            WeekendVisits       =("WeekendStop",        "sum"),
        )
        .reset_index()
        .rename(columns={"NearestZone": "ZoneName"})
    )
    agg = agg.sort_values("TotalVisits", ascending=False).round(2)
    logger.info(f"Zone summary built for {len(agg)} zone(s).")
    return agg
