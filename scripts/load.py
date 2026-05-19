# scripts/load.py

from pathlib import Path

import geopandas as gpd
import pandas as pd

from scripts.logger import logger
from scripts.config import (
    EXPORT_CSV, EXPORT_EXCEL,
    OUTPUT_CSV, OUTPUT_EXCEL,
)


def _ensure_dir(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────
# Individual exporters
# ─────────────────────────────────────────────

def export_csv(gdf: gpd.GeoDataFrame, filename: str = OUTPUT_CSV) -> None:
    """Export processed GeoDataFrame to CSV (geometry column dropped)."""
    _ensure_dir(filename)
    df = pd.DataFrame(gdf.drop(columns="geometry", errors="ignore"))
    df.to_csv(filename, index=False)
    logger.info(f"CSV exported: {filename} ({len(df)} rows).")


def export_excel(
    gdf: gpd.GeoDataFrame,
    device_summary: pd.DataFrame,
    zone_summary: pd.DataFrame,
    filename: str = OUTPUT_EXCEL,
) -> None:
    """
    Export to a multi-sheet Excel workbook:
        Sheet 1 – Processed Trips
        Sheet 2 – Device Summary
        Sheet 3 – Zone Summary
    """
    _ensure_dir(filename)
    df = pd.DataFrame(gdf.drop(columns="geometry", errors="ignore"))
    
    for col in df.select_dtypes(include=["datetimetz"]).columns:
        df[col] = df[col].dt.tz_localize(None)
    
    try:
        with pd.ExcelWriter(filename, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Processed Trips", index=False)
            if not device_summary.empty:
                device_summary.to_excel(writer, sheet_name="Device Summary", index=False)
            if not zone_summary.empty:
                zone_summary.to_excel(writer, sheet_name="Zone Summary", index=False)
        logger.info(f"Excel exported: {filename}.")
    except ImportError:
        logger.warning("openpyxl not installed — skipping Excel export.")
    except Exception as e:
        logger.error(f"Excel export failed: {e}")


# ─────────────────────────────────────────────
# Master export dispatcher
# ─────────────────────────────────────────────

def export_all(
    gdf: gpd.GeoDataFrame,
    device_summary: pd.DataFrame,
    zone_summary: pd.DataFrame,
) -> None:
    """
    Run all enabled exporters based on config flags.

    Args:
        gdf:            Fully-enriched trips GeoDataFrame.
        device_summary: Per-device aggregation DataFrame.
        zone_summary:   Per-zone aggregation DataFrame.
    """
    if EXPORT_CSV:
        export_csv(gdf)
    if EXPORT_EXCEL:
        export_excel(gdf, device_summary, zone_summary)
