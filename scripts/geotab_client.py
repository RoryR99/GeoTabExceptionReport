# scripts/geotab_client.py

import sys
import time
from mygeotab import API
from mygeotab.exceptions import AuthenticationException, MyGeotabException
from scripts.config import (
    GEOTAB_USERNAME, GEOTAB_PASSWORD, GEOTAB_DATABASE, GEOTAB_SERVER,
    API_MAX_RETRIES, API_RETRY_DELAY_S,
)
from scripts.logger import logger


def connect_to_geotab() -> API:
    """
    Authenticate with the GeoTab API.
    Exits with a clear error message on auth failure.
    """
    logger.info(f"Connecting to GeoTab API (server={GEOTAB_SERVER}, db={GEOTAB_DATABASE})...")
    try:
        api = API(
            username=GEOTAB_USERNAME,
            password=GEOTAB_PASSWORD,
            database=GEOTAB_DATABASE,
            server=GEOTAB_SERVER,
        )
        api.authenticate()
        logger.info("GeoTab authentication successful.")
        return api
    except AuthenticationException as e:
        logger.error(f"Authentication failed: {e}")
        sys.exit(1)


def api_get_with_retry(api: API, entity: str, search: dict = None, **kwargs):
    """
    Wrapper around api.get() with configurable retry/back-off on transient errors.

    Args:
        api:     Authenticated GeoTab API instance.
        entity:  GeoTab entity name (e.g. 'Trip', 'Zone', 'Device').
        search:  Optional search dict passed to api.get().
        **kwargs: Any additional keyword arguments forwarded to api.get().

    Returns:
        List of records returned by the API.

    Raises:
        MyGeotabException: After all retries are exhausted.
    """
    call_kwargs = {k: v for k, v in {"search": search, **kwargs}.items() if v is not None}
    last_exc = None

    for attempt in range(1, API_MAX_RETRIES + 1):
        try:
            logger.debug(f"api.get('{entity}') — attempt {attempt}/{API_MAX_RETRIES}")
            return api.get(entity, **call_kwargs)
        except MyGeotabException as exc:
            last_exc = exc
            if attempt < API_MAX_RETRIES:
                logger.warning(
                    f"api.get('{entity}') failed (attempt {attempt}): {exc}. "
                    f"Retrying in {API_RETRY_DELAY_S}s..."
                )
                time.sleep(API_RETRY_DELAY_S)
            else:
                logger.error(f"api.get('{entity}') failed after {API_MAX_RETRIES} attempts: {exc}")
                raise last_exc
