import sys
from mygeotab import API
from mygeotab.exceptions import AuthenticationException
from scripts.config import *
from scripts.logger import logger

def connect_to_geotab() -> API:
    try:
        logger.info("Connecting to GeoTab API...")
        api = API(
            username=GEOTAB_USERNAME,
            password=GEOTAB_PASSWORD,
            database=GEOTAB_DATABASE,
            server=GEOTAB_SERVER,
        )
        api.authenticate()
        logger.info("Connected")
        return api
    except AuthenticationException as e:
        logger.error(f"Auth failed: {e}")
        sys.exit(1)