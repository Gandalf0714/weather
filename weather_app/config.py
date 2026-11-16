"""Central configuration with environment-variable overrides."""

import os
from pathlib import Path


class Config:
    BASE_DIR = Path(__file__).resolve().parent.parent
    DATA_DIR = Path(os.getenv("WEATHER_DATA_DIR", BASE_DIR / "data"))
    CACHE_DIR = DATA_DIR / "cache"
    MODEL_DIR = DATA_DIR / "models"
    HTTP_TIMEOUT = int(os.getenv("WEATHER_HTTP_TIMEOUT", "20"))
    CACHE_TTL_SECONDS = int(os.getenv("WEATHER_CACHE_TTL", "1800"))
    MODEL_MAX_AGE_DAYS = int(os.getenv("WEATHER_MODEL_MAX_AGE_DAYS", "30"))
    HISTORY_YEARS = int(os.getenv("WEATHER_HISTORY_YEARS", "3"))
    JSON_AS_ASCII = False

    @classmethod
    def ensure_runtime_directories(cls):
        cls.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cls.MODEL_DIR.mkdir(parents=True, exist_ok=True)
