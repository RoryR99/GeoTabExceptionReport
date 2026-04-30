# GeoTab Spatial Current

Python ETL workflow for analyzing GeoTab trip stops against GeoTab zones. The project pulls recent trips and zones from the GeoTab API, performs geospatial nearest-zone analysis, exports processed CSV files, and can generate an interactive HTML map/report for stops that occurred outside zones for more than 10 minutes.

## What It Does

- Connects to the GeoTab API using credentials from a local `.env` file.
- Fetches GeoTab zones and recent trip records.
- Converts trips and zones into geospatial data.
- Identifies whether each stop is inside a zone.
- Calculates the nearest zone and distance for stops outside zones.
- Exports processed trip/stop results to CSV.
- Builds an optional Folium map and report for outside-zone stops over 10 minutes.

## Project Structure

```text
scripts/
  config.py          Environment variables and workflow settings
  geotab_client.py   GeoTab API authentication
  extract.py         GeoTab zone and trip extraction
  transform.py       Geospatial transformation and nearest-zone logic
  load.py            CSV export helper
  main.py            Main ETL workflow
  visualize.py       Optional map/report generator

requirements.txt     Python dependencies
Commands.txt         Quick command reference
.env.example         Environment variable template
```

Generated folders such as `output/`, `logs/`, virtual environments, and `.env` are intentionally ignored by Git.

## Requirements

- Python 3.10 or newer recommended
- GeoTab account credentials
- Access to the target GeoTab database

## Setup

Create and activate a virtual environment:

```powershell
python -m venv myenv
myenv\Scripts\activate
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Create your local environment file:

```powershell
copy .env.example .env
```

Then edit `.env` with your GeoTab credentials and settings.

## Environment Variables

Required:

```env
GEOTAB_DATABASE=your_database_name
GEOTAB_USERNAME=your_email@example.com
GEOTAB_PASSWORD=your_password
```

Optional:

```env
GEOTAB_SERVER=my.geotab.com
DAYS_BACK=7
OUTPUT_CSV=output/processed_truck_stops.csv
RAW_TRIPS_CSV=output/raw_trips.csv
```

Never commit your real `.env` file.

## Run the ETL

```powershell
python -m scripts.main
```

This creates:

```text
output/raw_trips.csv
output/processed_truck_stops.csv
```

## Generate Map and Report

After running the ETL, generate the optional map/report:

```powershell
python -m scripts.visualize
```

The visualization script asks for optional truck and zone filters. Leave the prompts blank to include all matching records.

This creates:

```text
output/stops_map.html
output/stops_report.csv
```

## Notes for Forking

Forked copies of this repository should include the source code and dependency list, but not private credentials or generated data. To run the project after forking:

1. Clone the fork.
2. Create a virtual environment.
3. Install `requirements.txt`.
4. Copy `.env.example` to `.env`.
5. Fill in GeoTab credentials.
6. Run `python -m scripts.main`.

## GitHub Push Reminder

If you make changes locally:

```powershell
git add .
git commit -m "Describe your change"
git push
```
