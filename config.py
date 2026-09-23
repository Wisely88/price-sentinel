import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "sentinel.db"

# Server configuration
HOST = os.getenv("SENTINEL_HOST", "0.0.0.0")
PORT = int(os.getenv("SENTINEL_PORT", "8765"))

# Default check interval in hours
DEFAULT_CHECK_INTERVAL_HOURS = 4

# Request settings
DEFAULT_TIMEOUT = 10.0
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
