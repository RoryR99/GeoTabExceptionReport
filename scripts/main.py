# scripts/main.py

from scripts.logger import logger
from scripts.config import DAYS_BACK, OUTPUT_CSV
from scripts.geotab_client import connect_to_geotab
from scripts.extract import fetch_zones, fetch_trips
from scripts.transform import create_trips_gdf, create_zones_gdf, spatial_join_nearest
from scripts.load import export_csv
from scripts.visualize import main as generate_visual_outputs


def main():
    logger.info("="*60)
    logger.info("Starting GeoTab ETL Workflow")
    logger.info("="*60)

    try:
        # -----------------------------
        # Connect to GeoTab API
        # -----------------------------
        api = connect_to_geotab()
        logger.info("Connected to GeoTab API")

        # -----------------------------
        # Fetch Zones
        # -----------------------------
        df_zones = fetch_zones(api)
        if df_zones.empty:
            logger.error("No zones fetched. Exiting workflow.")
            return
        zones_gdf = create_zones_gdf(df_zones)

        # -----------------------------
        # Fetch Trips
        # -----------------------------
        df_trips = fetch_trips(api, DAYS_BACK)
        if df_trips.empty:
            logger.warning("No trips fetched. Exiting workflow.")
            return
        trips_gdf = create_trips_gdf(df_trips)

        # -----------------------------
        # Spatial Join / Nearest Zone
        # -----------------------------
        results_gdf = spatial_join_nearest(trips_gdf, zones_gdf)
        total_trips = len(results_gdf)
        inside_count = results_gdf['InsideZone'].sum() if 'InsideZone' in results_gdf.columns else 0
        outside_count = total_trips - inside_count
        avg_distance = results_gdf['DistanceKm'].mean() if 'DistanceKm' in results_gdf.columns else 0
        outside_over_10min = 0
        if 'InsideZone' in results_gdf.columns and 'StopOver10Min' in results_gdf.columns:
            outside_over_10min = len(
                results_gdf[
                    (results_gdf['InsideZone'] == False) &
                    (results_gdf['StopOver10Min'] == True)
                ]
            )

        # -----------------------------
        # Export CSV
        # -----------------------------
        export_csv(results_gdf, OUTPUT_CSV)

        # -----------------------------
        # Workflow Summary
        # -----------------------------
        

        logger.info("="*60)
        logger.info("WORKFLOW SUMMARY")
        logger.info(f"Zones processed                 : {len(zones_gdf)}")
        logger.info(f"Trips processed                 : {total_trips}")
        logger.info(f"Trips inside zones              : {inside_count}")
        logger.info(f"Trips outside zones             : {outside_count}")
        logger.info(f"Trips outside zones >10 mins     : {outside_over_10min}")
        logger.info(f"Average distance to nearest zone: {avg_distance:.2f} km")
        logger.info("Workflow completed successfully")
        logger.info("="*60)

        # -----------------------------
        # Generate Map / Report
        # -----------------------------
        logger.info("Generating map and report outputs")
        generate_visual_outputs()

    except Exception as e:
        logger.exception(f"Workflow failed: {e}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.exception("Fatal error in workflow")
        raise

