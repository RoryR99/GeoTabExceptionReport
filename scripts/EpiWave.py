import os

import pandas as pd
import requests

from scripts.logger import logger


BASE_URL = os.getenv("EPICOR_BASE_URL", "https://centralusdtapp35.epicorsaas.com/saas853/api/v1")
USERNAME = os.getenv("EPICOR_USERNAME")
PASSWORD = os.getenv("EPICOR_PASSWORD")
BAQ_INTEGRATION = os.getenv("EPICOR_BAQ_INTEGRATION", "GeoTabIntegration-RR")
BAQ_WAVE_TRACK = os.getenv("EPICOR_BAQ_WAVE_TRACK", "GeoWaveDeviceTrack")
PAGE_SIZE = int(os.getenv("EPICOR_PAGE_SIZE", "1000"))

DEVICE_ID_COLUMNS = ("DeviceID", "DeviceId", "Device_ID", "GeoTabDeviceID", "GeoTab_DeviceID", "Calculated_DeviceID")
WAVE_COLUMNS = ("Wave", "WaveNum", "Wave_WaveNum", "WaveNumber", "UD12_Key1", "Calculated_Wave")
CUSTOMER_COLUMNS = ("Customer", "Customers", "CustomerName", "Customer_Name", "CustName", "Name", "Calculated_Customer")


def _first_value(row: dict, candidates: tuple[str, ...]) -> str:
    for column in candidates:
        value = row.get(column)
        if value is not None and str(value).strip():
            return str(value).strip()

    lower_candidates = {column.lower() for column in candidates}
    for column, value in row.items():
        if column.lower() in lower_candidates and value is not None and str(value).strip():
            return str(value).strip()

    return ""


def _first_matching_value(row: dict, candidates: tuple[str, ...], fragments: tuple[str, ...]) -> str:
    value = _first_value(row, candidates)
    if value:
        return value

    for column, value in row.items():
        normalized_column = column.lower()
        if any(fragment in normalized_column for fragment in fragments):
            if value is not None and str(value).strip():
                return str(value).strip()

    return ""


def download_baq(baq_name: str = BAQ_INTEGRATION) -> list[dict]:
    """Download all rows from an Epicor BAQ using paging."""
    if not USERNAME or not PASSWORD:
        return []

    url = f"{BASE_URL.rstrip('/')}/BaqSvc/{baq_name}"
    skip = 0
    all_rows = []

    while True:
        response = requests.get(
            url,
            auth=(USERNAME, PASSWORD),
            headers={"Accept": "application/json"},
            params={"$top": PAGE_SIZE, "$skip": skip},
            timeout=60,
        )
        response.raise_for_status()

        rows = response.json().get("value", [])
        if not rows:
            break

        all_rows.extend(rows)
        if len(rows) < PAGE_SIZE:
            break

        skip += PAGE_SIZE

    logger.info("%s: %s row(s) retrieved for Wave enrichment.", baq_name, len(all_rows))
    return all_rows


def build_wave_lookup(rows: list[dict]) -> dict[str, dict[str, str]]:
    """Build a lookup keyed by GeoTab device ID."""
    lookup = {}

    for row in rows:
        device_id = _first_matching_value(row, DEVICE_ID_COLUMNS, ("deviceid", "device_id", "geotab"))
        if not device_id:
            continue

        lookup[device_id] = {
            "Wave": _first_matching_value(row, WAVE_COLUMNS, ("wave",)),
            "Customer": _first_matching_value(row, CUSTOMER_COLUMNS, ("customer", "cust")),
        }

    logger.info("Wave lookup contains %s GeoTab device ID(s).", len(lookup))
    return lookup


def fetch_wave_lookup() -> dict[str, dict[str, str]]:
    """Fetch Epicor BAQ rows and return a GeoTab device enrichment lookup."""
    if not USERNAME or not PASSWORD:
        logger.warning("Epicor Wave enrichment skipped: EPICOR_USERNAME/EPICOR_PASSWORD not configured.")
        return {}

    integration_rows = download_baq(BAQ_INTEGRATION)
    if not integration_rows:
        return {}

    wave_track_rows = download_baq(BAQ_WAVE_TRACK)

    wave_track_lookup = {}
    for row in wave_track_rows:
        wave_number = _first_value(row, ("UD12_Key1",))
        if wave_number:
            wave_track_lookup[wave_number] = row

    joined_rows = []
    for integration_row in integration_rows:
        wave_number = _first_value(integration_row, ("Wave_WaveNum", "Wave", "WaveNum", "WaveNumber"))
        wave_track_row = wave_track_lookup.get(wave_number, {})
        joined_rows.append({**wave_track_row, **integration_row})

    return build_wave_lookup(joined_rows)


def enrich_with_wave(df: pd.DataFrame, wave_lookup: dict[str, dict[str, str]]) -> pd.DataFrame:
    """Add Wave and Customer columns to a DataFrame that contains DeviceID."""
    enriched = df.copy()

    if enriched.empty or "DeviceID" not in enriched.columns:
        return enriched

    device_ids = enriched["DeviceID"].astype(str).str.strip()
    enriched["Wave"] = device_ids.map(lambda value: wave_lookup.get(value, {}).get("Wave", ""))
    enriched["Customer"] = device_ids.map(lambda value: wave_lookup.get(value, {}).get("Customer", ""))
    return enriched
