import logging
from pathlib import Path

# Base project directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Logs folder
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

log_file = LOG_DIR / "geotab_etl.log"

# Configure logger
logging.basicConfig(
    level=logging.INFO,  # captures INFO + WARNING + ERROR
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()  # logs also to console
    ]
)

logger = logging.getLogger(__name__)

