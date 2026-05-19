# GeoTab ETL Pipeline

A production-grade Python ETL pipeline that connects to the GeoTab telematics API,
performs geospatial analysis on truck trip data, and exports enriched results in
multiple formats alongside interactive visual reports.

---

## Project Structure

```
geotab_etl/
├── scripts/
│   ├── main.py          # Pipeline orchestrator + CLI entry point
│   ├── config.py        # All settings (env-var driven)
│   ├── logger.py        # Rotating file logger with run-ID tagging
│   ├── geotab_client.py # API connection + retry wrapper
│   ├── extract.py       # Zones, devices, trips — raw data fetch
│   ├── transform.py     # Spatial join, feature engineering, summaries
│   ├── load.py          # CSV / Excel exporters
│   ├── validate.py      # Data quality checks
│   ├── visualize.py     # Folium map + HTML dashboard report
│   └── alerts.py        # Optional email notifications
├── tests/
│   └── test_transform.py
├── output/              # Generated data files (gitignored)
├── reports/             # Generated HTML reports (gitignored)
├── logs/                # Rotating log files (gitignored)
├── .env.example         # Copy to .env and fill in credentials
├── requirements.txt
└── test_env.py          # Quick dependency sanity check
```

---

## Quick Start

```bash
# 1. Clone / unzip and enter the project directory
cd geotab_etl

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure credentials
cp .env.example .env
# Edit .env with your GeoTab credentials

# 5. Verify your environment
python test_env.py

# 6. Run the pipeline
python -m scripts.main
```

---

## CLI Options

```
python -m scripts.main --help

  --days N        Look-back window in days (default: 30)
  --start-date    Explicit trip window start (YYYY-MM-DD or ISO datetime)
  --end-date      Explicit trip window end (YYYY-MM-DD or ISO datetime)
  --no-map        Skip Folium interactive map
  --no-report     Skip HTML dashboard report
  --dry-run       Validate config only, do not connect or fetch data
```

---

## Output Files

| File | Description |
|------|-------------|
| `output/processed_truck_stops.csv` | Main enriched trips data |
| `output/raw_trips.csv` | Raw trip data as fetched from API |
| `output/processed_truck_stops.xlsx` | Multi-sheet workbook (trips, device summary, zone summary) |
| `reports/trip_map.html` | Interactive Folium map with zones + trip markers for the selected trip window |
| `reports/etl_report.html` | HTML dashboard with KPI cards and tables for the selected trip window |
| `logs/geotab_etl.log` | Rotating log (5 MB × 5 backups) |

---

## Engineered Columns

| Column | Description |
|--------|-------------|
| `NearestZone` | Name of the closest zone polygon |
| `ZoneType` | Type of the nearest zone |
| `DistanceMeters` | Distance to nearest zone boundary (m) |
| `DistanceKm` | Distance to nearest zone boundary (km) |
| `InsideZone` | True if stop is within ZONE_BUFFER_METERS of zone |
| `ZoneLatitude/Longitude` | Centroid of nearest zone |
| `StopDurationMin` | Stop duration in minutes |
| `StopOver10Min` | Stop exceeded threshold duration |
| `LongStop` | Stop exceeded 60 minutes |
| `HighIdle` | Idling ticks above threshold |
| `AfterHoursStop` | Stop occurred outside business hours |
| `WeekendStop` | Stop occurred on a weekend |
| `DayOfWeek` | Human-readable day name |
| `HourOfStop` | Hour of stop time (0–23) |
| `FarFromZone` | Trip more than N km from any zone |
| `OutsideAndStopped` | Outside zone AND stopped > threshold |
| `SpeedKmh` | Estimated average trip speed |

---

## Configuration Reference

All settings are controlled via environment variables (`.env` file).
See `.env.example` for a full annotated reference.

Key thresholds:

| Variable | Default | Description |
|----------|---------|-------------|
| `DAYS_BACK` | 30 | Trip/report look-back window |
| `TRIP_START_DATE` | unset | Explicit trip window start; when set, use with `TRIP_END_DATE` |
| `TRIP_END_DATE` | unset | Explicit trip window end; when set, use with `TRIP_START_DATE` |
| `MAP_DAYS_BACK` | 7 | Legacy setting; map now follows the selected trip window |
| `ZONE_BUFFER_METERS` | 500 | Buffer to consider "inside zone" |
| `STOP_DURATION_THRESHOLD_MIN` | 10 | Short-stop flag threshold |
| `LONG_STOP_THRESHOLD_MIN` | 60 | Long-stop flag threshold |
| `AFTER_HOURS_START` | 18 | After-hours start (24h) |
| `FAR_FROM_ZONE_THRESHOLD_KM` | 5.0 | Flag trips farther than this |
| `API_MAX_RETRIES` | 3 | API call retry attempts |

When you provide `--start-date` and `--end-date` (or set `TRIP_START_DATE` and `TRIP_END_DATE`), the pipeline uses that exact date frame instead of calculating `now - DAYS_BACK`. Date-only values are expanded to full UTC-day boundaries. Both the HTML report and the Folium map display and use that same resolved window.

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Email Alerts

Set `ALERT_EMAIL_ENABLED=true` in your `.env` and configure the SMTP settings.
A summary email is sent on both successful completion and pipeline failure.
Gmail users should use an App Password (not their main password).
