#!/usr/bin/env python3
# scripts/main.py  (entry point — run from project root)

"""
GeoTab ETL Pipeline
───────────────────
Usage:
    python -m scripts.main                    # use .env defaults
    python -m scripts.main --days 14          # override look-back window
    python -m scripts.main --start-date 2026-05-01 --end-date 2026-05-12
    python -m scripts.main --no-map           # skip map generation
    python -m scripts.main --no-report        # skip HTML report
    python -m scripts.main --dry-run          # validate env/config only
"""

import argparse
import sys
import time
from datetime import datetime

from scripts.logger import logger
from scripts.config import (
    DAYS_BACK, TRIP_START_DATE, TRIP_END_DATE,
    GENERATE_HTML_REPORT, GENERATE_FOLIUM_MAP,
)
from scripts.geotab_client import connect_to_geotab
from scripts.extract import fetch_zones, fetch_trips, resolve_trip_window
from scripts.transform import (
    create_trips_gdf, create_zones_gdf,
    spatial_join_nearest, engineer_features,
    build_device_summary, build_zone_summary,
)
from scripts.load import export_all
from scripts.validate import validate_zones, validate_trips, validate_results
from scripts.visualize import generate_folium_map, generate_html_report
from scripts.alerts import send_summary_email
from scripts.EpiWave import enrich_with_wave, fetch_wave_lookup


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="GeoTab ETL Pipeline",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--days", type=int, default=DAYS_BACK,
        help="Number of days to look back for trips.",
    )
    parser.add_argument(
        "--start-date", default=TRIP_START_DATE,
        help="Explicit trip window start in ISO format (for example 2026-05-01).",
    )
    parser.add_argument(
        "--end-date", default=TRIP_END_DATE,
        help="Explicit trip window end in ISO format (for example 2026-05-12).",
    )
    parser.add_argument(
        "--no-map", action="store_true",
        help="Skip Folium interactive map generation.",
    )
    parser.add_argument(
        "--no-report", action="store_true",
        help="Skip HTML dashboard report generation.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Validate configuration and exit without running the pipeline.",
    )
    return parser.parse_args()




# ─────────────────────────────────────────────
# Pipeline
# ─────────────────────────────────────────────

def main() -> None:
    args = parse_args()
    run_start = time.time()
    window_start, window_end = resolve_trip_window(
        days_back=args.days,
        start_date=args.start_date,
        end_date=args.end_date,
    )

    logger.info("=" * 60)
    logger.info("GeoTab ETL Pipeline — starting")
    if args.start_date or args.end_date:
        logger.info("Trip window      : %s to %s", window_start.isoformat(), window_end.isoformat())
    else:
        logger.info(f"Look-back window : {args.days} day(s)")
    logger.info("=" * 60)

    if args.dry_run:
        logger.info("Dry-run mode — configuration OK. Exiting.")
        return

    try:
        # ── Step 1: Connect ──────────────────────────────────────────
        api = connect_to_geotab()

        # ── Step 2: Extract ──────────────────────────────────────────
        df_zones = fetch_zones(api)
        df_trips = fetch_trips(
            api,
            days_back=args.days,
            start_date=args.start_date,
            end_date=args.end_date,
        )

        # ── Step 3: Validate raw data ────────────────────────────────
        validate_zones(df_zones)
        validate_trips(df_trips)

        if df_zones.empty:
            logger.error("No zones fetched. Cannot proceed with spatial analysis.")
            send_summary_email({"error": "No zones fetched"}, success=False)
            sys.exit(1)

        if df_trips.empty:
            logger.warning("No trips fetched for the given period. Nothing to process.")
            send_summary_email({"warning": "No trips fetched"}, success=False)
            return

        # ── Step 4: Transform ────────────────────────────────────────
        zones_gdf = create_zones_gdf(df_zones)
        trips_gdf = create_trips_gdf(df_trips)

        results_gdf = spatial_join_nearest(trips_gdf, zones_gdf)
        results_gdf = engineer_features(results_gdf)
        wave_lookup = fetch_wave_lookup()
        if wave_lookup:
            results_gdf = enrich_with_wave(results_gdf, wave_lookup)

        device_summary = build_device_summary(results_gdf)
        zone_summary   = build_zone_summary(results_gdf)

        # ── Step 5: Validate results ─────────────────────────────────
        stats = validate_results(results_gdf)

        # ── Step 6: Load / export ────────────────────────────────────
        export_all(results_gdf, device_summary, zone_summary)

        # ── Step 7: Visualise ────────────────────────────────────────
        if GENERATE_FOLIUM_MAP and not args.no_map:
            generate_folium_map(
                results_gdf,
                zones_gdf,
                window_start=window_start,
                window_end=window_end,
            )
        if GENERATE_HTML_REPORT and not args.no_report:
            generate_html_report(
                results_gdf,
                device_summary,
                zone_summary,
                window_start=window_start,
                window_end=window_end,
            )

        # ── Step 8: Summary ──────────────────────────────────────────
        elapsed = round(time.time() - run_start, 1)

        logger.info("=" * 60)
        logger.info("WORKFLOW SUMMARY")
        logger.info(f"  Zones processed              : {len(zones_gdf)}")
        logger.info(f"  Trips processed              : {stats['total_trips']}")
        logger.info(f"  Inside zone                  : {stats['total_trips'] - stats['outside_zone']}")
        logger.info(f"  Outside zone                 : {stats['outside_zone']}")
        logger.info(f"  After-hours stops            : {stats['after_hours']}")
        logger.info(f"  Weekend stops                : {stats['weekend_stops']}")
        logger.info(f"  Long stops (>60 min)         : {stats['long_stops']}")
        logger.info(f"  High-idle events             : {stats['high_idle']}")
        logger.info(f"  Far-from-zone trips          : {stats['far_from_zone']}")
        logger.info(f"  Elapsed time                 : {elapsed}s")
        logger.info("Workflow completed successfully.")
        logger.info("=" * 60)

        send_summary_email(
            {**stats, "elapsed_seconds": elapsed, "run_time": datetime.now().isoformat()},
            success=True,
        )

    except Exception as exc:
        logger.exception(f"Workflow failed: {exc}")
        send_summary_email({"error": str(exc)}, success=False)
        raise


if __name__ == "__main__":
    main()
