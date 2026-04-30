import os
from dotenv import load_dotenv

load_dotenv()

# -----------------------------
# GeoTab connection settings
# -----------------------------
GEOTAB_DATABASE = os.getenv("GEOTAB_DATABASE")
GEOTAB_USERNAME = os.getenv("GEOTAB_USERNAME")
GEOTAB_PASSWORD = os.getenv("GEOTAB_PASSWORD")
GEOTAB_SERVER = os.getenv("GEOTAB_SERVER", "my.geotab.com")

# -----------------------------
# Workflow settings
# -----------------------------
DAYS_BACK = int(os.getenv("DAYS_BACK", 7))
OUTPUT_CSV = os.getenv("OUTPUT_CSV", "output/processed_truck_stops.csv")

# CSV for raw trips dump
RAW_TRIPS_CSV = os.getenv("RAW_TRIPS_CSV", "output/raw_trips.csv")

# -----------------------------
# CRS for geospatial calculations
# -----------------------------
METRIC_CRS = "EPSG:3857"
GEOGRAPHIC_CRS = "EPSG:4326"

