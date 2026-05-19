# scripts/config.py

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# -----------------------------
# Base paths
# -----------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "output"
LOG_DIR = BASE_DIR / "logs"
REPORTS_DIR = BASE_DIR / "reports"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# -----------------------------
# GeoTab connection settings
# -----------------------------
GEOTAB_DATABASE = os.getenv("GEOTAB_DATABASE")
GEOTAB_USERNAME = os.getenv("GEOTAB_USERNAME")
GEOTAB_PASSWORD = os.getenv("GEOTAB_PASSWORD")
GEOTAB_SERVER   = os.getenv("GEOTAB_SERVER", "my.geotab.com")

# Validate required credentials
_REQUIRED = {
    "GEOTAB_DATABASE": GEOTAB_DATABASE,
    "GEOTAB_USERNAME": GEOTAB_USERNAME,
    "GEOTAB_PASSWORD": GEOTAB_PASSWORD,
}
_MISSING = [k for k, v in _REQUIRED.items() if not v]
if _MISSING:
    raise EnvironmentError(
        f"Missing required environment variables: {', '.join(_MISSING)}. "
        "Please check your .env file."
    )

# -----------------------------
# Workflow settings
# -----------------------------
DAYS_BACK      = int(os.getenv("DAYS_BACK", 30))
TRIP_START_DATE = os.getenv("TRIP_START_DATE")
TRIP_END_DATE   = os.getenv("TRIP_END_DATE")
MAP_DAYS_BACK  = int(os.getenv("MAP_DAYS_BACK", 7))
OUTPUT_CSV     = os.getenv("OUTPUT_CSV",     str(OUTPUT_DIR / "processed_truck_stops.csv"))
RAW_TRIPS_CSV  = os.getenv("RAW_TRIPS_CSV",  str(OUTPUT_DIR / "raw_trips.csv"))
OUTPUT_EXCEL   = os.getenv("OUTPUT_EXCEL",   str(OUTPUT_DIR / "processed_truck_stops.xlsx"))

# Enable/disable output formats
EXPORT_CSV     = os.getenv("EXPORT_CSV",     "true").lower() == "true"
EXPORT_EXCEL   = os.getenv("EXPORT_EXCEL",   "true").lower() == "true"

# -----------------------------
# Spatial / CRS settings
# -----------------------------
METRIC_CRS     = "EPSG:3857"
GEOGRAPHIC_CRS = "EPSG:4326"

# Buffer around zone boundary to consider a trip "inside" (metres)
ZONE_BUFFER_METERS = int(os.getenv("ZONE_BUFFER_METERS", 500))

# -----------------------------
# Business logic thresholds
# -----------------------------
STOP_DURATION_THRESHOLD_MIN   = int(os.getenv("STOP_DURATION_THRESHOLD_MIN", 10))
LONG_STOP_THRESHOLD_MIN       = int(os.getenv("LONG_STOP_THRESHOLD_MIN", 60))
AFTER_HOURS_START             = int(os.getenv("AFTER_HOURS_START", 18))   # 6 PM
AFTER_HOURS_END               = int(os.getenv("AFTER_HOURS_END",   6))    # 6 AM
WEEKEND_DAYS                  = [5, 6]   # Saturday=5, Sunday=6
IDLE_THRESHOLD_TICKS          = int(os.getenv("IDLE_THRESHOLD_TICKS", 600))   # ~10 min
FAR_FROM_ZONE_THRESHOLD_KM    = float(os.getenv("FAR_FROM_ZONE_THRESHOLD_KM", 5.0))

# -----------------------------
# API retry settings
# -----------------------------
API_MAX_RETRIES   = int(os.getenv("API_MAX_RETRIES", 3))
API_RETRY_DELAY_S = float(os.getenv("API_RETRY_DELAY_S", 5.0))

# -----------------------------
# Alerting (optional email)
# -----------------------------
ALERT_EMAIL_ENABLED  = os.getenv("ALERT_EMAIL_ENABLED",  "false").lower() == "true"
ALERT_EMAIL_TO       = os.getenv("ALERT_EMAIL_TO",       "")
ALERT_EMAIL_FROM     = os.getenv("ALERT_EMAIL_FROM",     "")
ALERT_SMTP_HOST      = os.getenv("ALERT_SMTP_HOST",      "smtp.gmail.com")
ALERT_SMTP_PORT      = int(os.getenv("ALERT_SMTP_PORT",  587))
ALERT_SMTP_PASSWORD  = os.getenv("ALERT_SMTP_PASSWORD",  "")

# -----------------------------
# Report / map settings
# -----------------------------
GENERATE_HTML_REPORT = os.getenv("GENERATE_HTML_REPORT", "true").lower() == "true"
GENERATE_FOLIUM_MAP  = os.getenv("GENERATE_FOLIUM_MAP",  "true").lower() == "true"
HTML_REPORT_PATH     = os.getenv("HTML_REPORT_PATH",     str(REPORTS_DIR / "etl_report.html"))
FOLIUM_MAP_PATH      = os.getenv("FOLIUM_MAP_PATH",      str(REPORTS_DIR / "trip_map.html"))
