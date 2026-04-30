# scripts/extract.py

import pandas as pd
from datetime import datetime, timedelta, timezone
from mygeotab.exceptions import MyGeotabException
from scripts.logger import logger
from scripts.config import RAW_TRIPS_CSV

def fetch_zones(api) -> pd.DataFrame:
    """
    Fetch zones from GeoTab API and return as a DataFrame.
    """
    logger.info("Fetching zones...")
    try:
        zones = api.get("Zone")
        zone_data = []

        for z in zones:
            points = z.get("points", [])
            if not points or not isinstance(points, list):
                continue

            coords = [(p["x"], p["y"]) for p in points if "x" in p and "y" in p]
            if len(coords) < 3:
                continue

            zone_data.append({
                "ZoneID": z.get("id", ""),
                "ZoneName": z.get("name", "Unknown"),
                "Points": coords,
                "Comment": z.get("comment", ""),
                "ActiveFrom": z.get("activeFrom"),
                "ActiveTo": z.get("activeTo")
            })

        df = pd.DataFrame(zone_data)
        logger.info(f"Fetched {len(df)} zones")
        return df

    except MyGeotabException as e:
        logger.error(f"Error fetching zones: {e}")
        return pd.DataFrame()

import pandas as pd
from scripts.config import RAW_TRIPS_CSV

def fetch_trips(api, days_back: int = 7) -> pd.DataFrame:
    """
    Fetch all trips for the last N days.
    Use StopPointX/StopPointY if available; fallback to endAddress coordinates.
    Raw data is exported to CSV immediately after fetch.
    """
    logger.info(f"Fetching trips from last {days_back} days...")

    to_date = datetime.now(timezone.utc)
    from_date = to_date - timedelta(days=days_back)

    try:
        # Fetch devices for mapping
        devices = api.get("Device")
        device_map = {d["id"]: d["name"] for d in devices}

        # Fetch trips
        trips = api.get("Trip", search={
            "fromDate": from_date.isoformat(),
            "toDate": to_date.isoformat()
        })

        trip_data = []

        for trip in trips:
            device_id = trip.get("device", {}).get("id", "")

            stop_point = trip.get("stopPoint", {})
            latitude = stop_point.get("y")
            longitude = stop_point.get("x")

            trip_data.append({
                "TripID": trip.get("id"),
                "DeviceID": device_id,
                "DeviceName": device_map.get(device_id, "Unknown"),
                "StartTime": trip.get("start"),
                "StopTime": trip.get("stop"),
                "Latitude": latitude,
                "Longitude": longitude,
                "Distance": trip.get("distance"),
                "DurationStop": trip.get("workStopDuration"),
                "IdlingTicks": trip.get("idlingDurationTicks"),
                "WorkDistance": trip.get("workDistance"),
                "AfterHoursDistance": trip.get("afterHoursDistance"),
                "EntityStatus": trip.get("entityStatus")
        })


        df = pd.DataFrame(trip_data)
        logger.info(f"Fetched {len(df)} trips")

        # Dump raw trips to CSV immediately
        df.to_csv(RAW_TRIPS_CSV, index=False)
        logger.info(f"Raw trips data exported to {RAW_TRIPS_CSV}")

        return df

    except MyGeotabException as e:
        logger.error(f"Error fetching trips: {e}")
        return pd.DataFrame()
