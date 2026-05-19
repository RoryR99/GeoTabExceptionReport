# scripts/extract.py

import pandas as pd
from datetime import datetime, timedelta, timezone

from scripts.logger import logger
from scripts.config import RAW_TRIPS_CSV
from scripts.geotab_client import api_get_with_retry


def _parse_window_boundary(value, *, boundary: str) -> datetime:
    """Parse a CLI/env date value into a UTC datetime boundary."""
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            raise ValueError("Date value cannot be empty.")

        try:
            if "T" in text or " " in text:
                dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            else:
                day = datetime.fromisoformat(text).date()
                if boundary == "start":
                    dt = datetime.combine(day, datetime.min.time())
                else:
                    dt = datetime.combine(day, datetime.max.time())
        except ValueError as exc:
            raise ValueError(
                f"Invalid {boundary} date '{value}'. Use ISO format like YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS."
            ) from exc

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    return dt


def resolve_trip_window(
    *,
    days_back: int | None = 30,
    start_date=None,
    end_date=None,
    now: datetime | None = None,
) -> tuple[datetime, datetime]:
    """
    Resolve the trip fetch window in UTC.

    Priority:
    1. Explicit start/end date frame
    2. Relative look-back window via days_back
    """
    has_start = start_date is not None
    has_end = end_date is not None

    if has_start or has_end:
        if not (has_start and has_end):
            raise ValueError("Both start_date and end_date must be provided together.")

        from_date = _parse_window_boundary(start_date, boundary="start")
        to_date = _parse_window_boundary(end_date, boundary="end")
    else:
        if days_back is None:
            raise ValueError("days_back is required when no explicit date frame is provided.")
        if days_back < 0:
            raise ValueError("days_back must be greater than or equal to 0.")

        current_time = now.astimezone(timezone.utc) if now else datetime.now(timezone.utc)
        to_date = current_time
        from_date = to_date - timedelta(days=days_back)

    if from_date > to_date:
        raise ValueError("start_date must be earlier than or equal to end_date.")

    return from_date, to_date


# ─────────────────────────────────────────────
# Zones
# ─────────────────────────────────────────────

def fetch_zones(api) -> pd.DataFrame:
    """
    Fetch all zones from the GeoTab API.

    Returns:
        DataFrame with columns: ZoneID, ZoneName, Points, Comment,
        ActiveFrom, ActiveTo, ZoneType.
    """
    logger.info("Fetching zones...")
    zones = api_get_with_retry(api, "Zone")

    zone_data = []
    for z in zones:
        points = z.get("points", [])
        if not points or not isinstance(points, list):
            continue
        coords = [(p["x"], p["y"]) for p in points if "x" in p and "y" in p]
        if len(coords) < 3:
            continue

        zone_type = z.get("zoneTypes", [])
        if zone_type:
            first = zone_type[0]
            zone_type_name = first.get("name", str(first)) if isinstance(first, dict) else str(first)
        else:
            zone_type_name = "Unknown"

        zone_data.append({
            "ZoneID":     z.get("id", ""),
            "ZoneName":   z.get("name", "Unknown"),
            "Points":     coords,
            "Comment":    z.get("comment", ""),
            "ActiveFrom": z.get("activeFrom"),
            "ActiveTo":   z.get("activeTo"),
            "ZoneType":   zone_type_name,
        })

    df = pd.DataFrame(zone_data)
    logger.info(f"Fetched {len(df)} valid zones.")
    return df


# ─────────────────────────────────────────────
# Devices
# ─────────────────────────────────────────────

def fetch_devices(api) -> dict:
    """
    Fetch all devices and return a mapping of device ID → device info dict.

    Returns:
        dict: {device_id: {"name": ..., "licensePlate": ..., "vehicleType": ...}}
    """
    logger.info("Fetching devices...")
    devices = api_get_with_retry(api, "Device")
    device_map = {}
    for d in devices:
        device_map[d["id"]] = {
            "name":         d.get("name", "Unknown"),
            "licensePlate": d.get("licensePlate", ""),
            "vehicleType":  d.get("vehicleIdentificationNumber", ""),
            "comment":      d.get("comment", ""),
        }
    logger.info(f"Fetched {len(device_map)} devices.")
    return device_map


# ─────────────────────────────────────────────
# Trips
# ─────────────────────────────────────────────

def fetch_trips(api, days_back: int = 30, start_date=None, end_date=None) -> pd.DataFrame:
    """
    Fetch all trips for the last N days from the GeoTab API.

    Enriches each trip with device metadata. Raw data is written to CSV
    immediately after fetch for debugging/auditing purposes.

    Args:
        api:        Authenticated GeoTab API instance.
        days_back:  Number of days to look back from now.
        start_date: Explicit window start (optional).
        end_date:   Explicit window end (optional).

    Returns:
        DataFrame with one row per trip.
    """
    from_date, to_date = resolve_trip_window(
        days_back=days_back,
        start_date=start_date,
        end_date=end_date,
    )
    logger.info(
        "Fetching trips from %s to %s...",
        from_date.isoformat(),
        to_date.isoformat(),
    )

    device_map = fetch_devices(api)

    trips = api_get_with_retry(
        api, "Trip",
        search={
            "fromDate": from_date.isoformat(),
            "toDate":   to_date.isoformat(),
        }
    )

    trip_data = []
    for trip in trips:
        device_id   = trip.get("device", {}).get("id", "")
        device_info = device_map.get(device_id, {})

        stop_point = trip.get("stopPoint", {}) or {}
        latitude   = stop_point.get("y")
        longitude  = stop_point.get("x")

        start_time = trip.get("start")
        stop_time  = trip.get("stop")

        # Duration (minutes) from start to stop
        trip_duration_min = None
        if start_time and stop_time:
            try:
                if hasattr(start_time, "timestamp"):
                    delta = (stop_time - start_time).total_seconds() / 60
                else:
                    fmt = "%Y-%m-%dT%H:%M:%S.%f%z"
                    delta = (
                        datetime.fromisoformat(str(stop_time)) -
                        datetime.fromisoformat(str(start_time))
                    ).total_seconds() / 60
                    delta = delta
                trip_duration_min = round(delta, 2)
            except Exception:
                pass

        trip_data.append({
            "TripID":              trip.get("id"),
            "DeviceID":            device_id,
            "DeviceName":          device_info.get("name", "Unknown"),
            "LicensePlate":        device_info.get("licensePlate", ""),
            "VehicleType":         device_info.get("vehicleType", ""),
            "DeviceComment":       device_info.get("comment", ""),
            "StartTime":           start_time,
            "StopTime":            stop_time,
            "TripDurationMin":     trip_duration_min,
            "Latitude":            latitude,
            "Longitude":           longitude,
            "Distance":            trip.get("distance"),
            "DurationStop":        trip.get("workStopDuration"),
            "IdlingTicks":         trip.get("idlingDurationTicks"),
            "WorkDistance":        trip.get("workDistance"),
            "AfterHoursDistance":  trip.get("afterHoursDistance"),
            "EntityStatus":        trip.get("entityStatus"),
        })

    df = pd.DataFrame(trip_data)
    logger.info(f"Fetched {len(df)} trips.")

    # Dump raw trips immediately for audit/debugging
    try:
        df.to_csv(RAW_TRIPS_CSV, index=False)
        logger.info(f"Raw trips exported to {RAW_TRIPS_CSV}.")
    except Exception as e:
        logger.warning(f"Could not write raw trips CSV: {e}")

    return df
