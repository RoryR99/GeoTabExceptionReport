# scripts/logger.py

import logging
import uuid
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Base project directory
BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR  = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

log_file = LOG_DIR / "geotab_etl.log"

# Unique run ID stamped on every log line
RUN_ID = str(uuid.uuid4())[:8]

LOG_FORMAT = f"%(asctime)s | %(levelname)-8s | run={RUN_ID} | %(name)s | %(message)s"

# Root handlers
_file_handler   = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=5)
_stream_handler = logging.StreamHandler()

for _h in (_file_handler, _stream_handler):
    _h.setFormatter(logging.Formatter(LOG_FORMAT))

logging.basicConfig(level=logging.INFO, handlers=[_file_handler, _stream_handler])

logger = logging.getLogger("geotab_etl")
logger.info(f"Logger initialised — run_id={RUN_ID}, log={log_file}")
