# scripts/validate.py

"""
Data quality validation module.

Runs a suite of checks on the raw and processed DataFrames and logs
warnings for any anomalies found. Does not raise exceptions — the
pipeline continues regardless, but issues are clearly flagged.
"""

import pandas as pd
import geopandas as gpd

from scripts.logger import logger


def validate_zones(df: pd.DataFrame) -> None:
    """Run data quality checks on the raw zones DataFrame."""
    issues = []

    if df.empty:
        logger.error("Validation: zones DataFrame is empty.")
        return

    null_names = df["ZoneName"].isna().sum() if "ZoneName" in df.columns else 0
    if null_names:
        issues.append(f"{null_names} zones have null ZoneName.")

    dupe_names = df.duplicated(subset=["ZoneName"]).sum() if "ZoneName" in df.columns else 0
    if dupe_names:
        issues.append(f"{dupe_names} duplicate zone names detected.")

    small_polys = df[df["Points"].apply(lambda p: len(p) < 4)].shape[0] if "Points" in df.columns else 0
    if small_polys:
        issues.append(f"{small_polys} zones have fewer than 4 boundary points.")

    if issues:
        for issue in issues:
            logger.warning(f"Zone validation: {issue}")
    else:
        logger.info(f"Zone validation passed ({len(df)} zones).")


def validate_trips(df: pd.DataFrame) -> None:
    """Run data quality checks on the raw trips DataFrame."""
    issues = []

    if df.empty:
        logger.warning("Validation: trips DataFrame is empty.")
        return

    missing_coords = df[["Latitude", "Longitude"]].isna().any(axis=1).sum()
    if missing_coords:
        issues.append(f"{missing_coords} trips missing coordinates.")

    if "Latitude" in df.columns:
        out_of_range = df[(df["Latitude"].abs() > 90) | (df["Longitude"].abs() > 180)].shape[0]
        if out_of_range:
            issues.append(f"{out_of_range} trips with out-of-range lat/lon values.")

    dupe_trips = df.duplicated(subset=["TripID"]).sum() if "TripID" in df.columns else 0
    if dupe_trips:
        issues.append(f"{dupe_trips} duplicate TripIDs detected.")

    if "StartTime" in df.columns and "StopTime" in df.columns:
        starts = pd.to_datetime(df["StartTime"], errors="coerce", utc=True)
        stops  = pd.to_datetime(df["StopTime"],  errors="coerce", utc=True)
        inverted = (stops < starts).sum()
        if inverted:
            issues.append(f"{inverted} trips where StopTime < StartTime.")

    if issues:
        for issue in issues:
            logger.warning(f"Trip validation: {issue}")
    else:
        logger.info(f"Trip validation passed ({len(df)} trips).")


def validate_results(gdf: gpd.GeoDataFrame) -> dict:
    """
    Run final checks on the processed GeoDataFrame and return a summary dict.

    Returns:
        dict with counts of anomalies for use in email alerts / reports.
    """
    df = pd.DataFrame(gdf.drop(columns="geometry", errors="ignore"))

    summary = {
        "total_trips":         len(df),
        "unmatched_zones":     int(df["NearestZone"].isna().sum()) if "NearestZone" in df.columns else 0,
        "outside_zone":        int((~df["InsideZone"].fillna(False)  ).sum()) if "InsideZone" in df.columns else 0,
        "after_hours":         int(df["AfterHoursStop"].sum())  if "AfterHoursStop" in df.columns else 0,
        "weekend_stops":       int(df["WeekendStop"].sum())     if "WeekendStop"    in df.columns else 0,
        "long_stops":          int(df["LongStop"].sum())        if "LongStop"       in df.columns else 0,
        "high_idle":           int(df["HighIdle"].sum())        if "HighIdle"       in df.columns else 0,
        "far_from_zone":       int(df["FarFromZone"].sum())     if "FarFromZone"    in df.columns else 0,
    }

    # Log any notable anomalies
    if summary["unmatched_zones"]:
        logger.warning(f"{summary['unmatched_zones']} trips could not be matched to any zone.")
    if summary["after_hours"]:
        logger.warning(f"{summary['after_hours']} after-hours stops detected.")
    if summary["far_from_zone"]:
        logger.warning(f"{summary['far_from_zone']} trips are far from any zone (>threshold km).")

    logger.info(f"Result validation complete: {summary}")
    return summary
