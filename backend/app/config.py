import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = BASE_DIR / "frontend"
SEED_FILE = Path(__file__).resolve().parent / "seed_data.json"

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://frostbase:frostbase@localhost:5433/frostbase",
)
SECRET = os.getenv("FROSTBASE_SECRET", "frostbase-development-secret")
TOKEN_TTL_HOURS = int(os.getenv("FROSTBASE_TOKEN_TTL_HOURS", "12"))
AUTO_SEED = os.getenv("AUTO_SEED", "true").lower() in {"1", "true", "yes", "on"}
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:8000,http://127.0.0.1:8000,http://localhost:5173",
    ).split(",")
    if origin.strip()
]
BASE_LOCATION = {"latitude": 32.45900929216648, "longitude": -116.97966765227373}
