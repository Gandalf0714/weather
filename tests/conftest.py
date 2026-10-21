import numpy as np
import pandas as pd
import pytest

from weather_app import create_app
from weather_app.config import Config


class TestConfig(Config):
    TESTING = True


@pytest.fixture()
def app(tmp_path):
    class LocalConfig(TestConfig):
        DATA_DIR = tmp_path
        CACHE_DIR = tmp_path / "cache"
        MODEL_DIR = tmp_path / "models"

    return create_app(LocalConfig)


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def weather_frame():
    rng = np.random.default_rng(42)
    dates = pd.date_range("2023-01-01", periods=520, freq="D")
    season = np.sin(2 * np.pi * dates.dayofyear / 365.25)
    high = 11 + 22 * season + rng.normal(0, 2, len(dates))
    low = high - 9 + rng.normal(0, 1.2, len(dates))
    rain = np.maximum(0, rng.gamma(1.1, 2.2, len(dates)) - 1.5)
    codes = np.where(rain > 7, 65, np.where(rain > 1, 61, np.where(season > 0, 1, 3)))
    return pd.DataFrame(
        {
            "date": dates,
            "weather_code": codes,
            "temperature_2m_max": high,
            "temperature_2m_min": low,
            "precipitation_sum": rain,
            "wind_speed_10m_max": 12 + rng.normal(0, 3, len(dates)),
            "us_aqi": 65 - 12 * season + rng.normal(0, 8, len(dates)),
        }
    )
