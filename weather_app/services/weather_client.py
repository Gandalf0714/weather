"""Open-Meteo client with disk caching and resilient stale-cache fallback."""

import hashlib
import json
from datetime import date, timedelta
from pathlib import Path
from time import time

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from weather_app.services.locations import Location


class WeatherDataError(RuntimeError):
    """Raised when upstream weather data cannot be obtained or validated."""


class WeatherClient:
    FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
    ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
    AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
    GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"

    CURRENT_FIELDS = (
        "temperature_2m,relative_humidity_2m,apparent_temperature,is_day,"
        "precipitation,weather_code,cloud_cover,surface_pressure,"
        "wind_speed_10m,wind_direction_10m"
    )
    DAILY_FIELDS = (
        "weather_code,temperature_2m_max,temperature_2m_min,"
        "apparent_temperature_max,apparent_temperature_min,sunrise,sunset,"
        "uv_index_max,precipitation_sum,precipitation_probability_max,"
        "wind_speed_10m_max"
    )
    HOURLY_FIELDS = (
        "temperature_2m,apparent_temperature,precipitation_probability,"
        "weather_code,wind_speed_10m"
    )
    AIR_FIELDS = "us_aqi,pm2_5,pm10,nitrogen_dioxide,ozone"

    def __init__(self, cache_dir: Path, timeout=20, ttl_seconds=1800):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.ttl_seconds = ttl_seconds
        self.session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.session.headers.update({"User-Agent": "WeatherML/2.0"})

    def _cache_path(self, url, params):
        serialized = json.dumps([url, params], sort_keys=True, ensure_ascii=True)
        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}.json"

    def _read_cache(self, path, allow_stale=False):
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            is_fresh = time() - payload["cached_at"] <= self.ttl_seconds
            if is_fresh or allow_stale:
                return payload["data"]
        except (KeyError, OSError, ValueError, TypeError):
            return None
        return None

    def _get(self, url, params, cache=True):
        cache_path = self._cache_path(url, params)
        if cache:
            fresh = self._read_cache(cache_path)
            if fresh is not None:
                return fresh

        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            if "error" in data and data["error"]:
                raise WeatherDataError(data.get("reason", "天气服务返回错误"))
            if cache:
                cache_path.write_text(
                    json.dumps(
                        {"cached_at": time(), "data": data},
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
            return data
        except (requests.RequestException, ValueError, OSError) as exc:
            stale = self._read_cache(cache_path, allow_stale=True) if cache else None
            if stale is not None:
                stale["_stale_cache"] = True
                return stale
            raise WeatherDataError(f"天气数据服务暂时不可用: {exc}") from exc

    def search_locations(self, query, count=6):
        data = self._get(
            self.GEOCODING_URL,
            {
                "name": query,
                "count": count,
                "language": "zh",
                "format": "json",
            },
        )
        results = []
        for item in data.get("results", []):
            if item.get("country_code") not in {"CN", "HK", "MO", "TW"}:
                continue
            results.append(
                Location(
                    name=item["name"],
                    province=item.get("admin1") or item.get("country") or "中国",
                    latitude=float(item["latitude"]),
                    longitude=float(item["longitude"]),
                    timezone=item.get("timezone") or "Asia/Shanghai",
                )
            )
        return results

    def get_dashboard(self, location: Location):
        common = {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "timezone": location.timezone,
        }
        forecast = self._get(
            self.FORECAST_URL,
            {
                **common,
                "current": self.CURRENT_FIELDS,
                "hourly": self.HOURLY_FIELDS,
                "daily": self.DAILY_FIELDS,
                "past_days": 7,
                "forecast_days": 8,
            },
        )
        air = self._get(
            self.AIR_URL,
            {**common, "current": self.AIR_FIELDS, "hourly": "us_aqi"},
        )
        return self._normalize_dashboard(location, forecast, air)

    def _normalize_dashboard(self, location, forecast, air):
        current = dict(forecast.get("current", {}))
        current.update({f"air_{key}": value for key, value in air.get("current", {}).items()})
        daily = self._records(forecast.get("daily", {}))
        hourly = self._records(forecast.get("hourly", {}))
        today = str(current.get("time", ""))[:10] or date.today().isoformat()
        history = [row for row in daily if row.get("time", "") < today][-7:]
        future = [row for row in daily if row.get("time", "") >= today][:7]
        current_hour = str(current.get("time", ""))[:13]
        next_hours = [row for row in hourly if row.get("time", "")[:13] >= current_hour][:24]
        return {
            "location": location.to_dict(),
            "current": current,
            "hourly": next_hours,
            "observed_history": history,
            "forecast_reference": future,
            "source": "Open-Meteo",
            "stale": bool(forecast.get("_stale_cache") or air.get("_stale_cache")),
        }

    @staticmethod
    def _records(block):
        times = block.get("time", [])
        fields = [key for key in block if key != "time"]
        return [
            {"time": timestamp, **{field: block[field][index] for field in fields}}
            for index, timestamp in enumerate(times)
        ]

    def get_training_frame(self, location: Location, years=3):
        end_date = date.today() - timedelta(days=6)
        start_date = end_date - timedelta(days=365 * years)
        common = {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "timezone": location.timezone,
        }
        weather = self._get(
            self.ARCHIVE_URL,
            {
                **common,
                "daily": (
                    "weather_code,temperature_2m_max,temperature_2m_min,"
                    "precipitation_sum,wind_speed_10m_max"
                ),
            },
        )
        air = self._get(self.AIR_URL, {**common, "hourly": "us_aqi"})
        weather_frame = pd.DataFrame(weather.get("daily", {})).rename(columns={"time": "date"})
        air_frame = pd.DataFrame(air.get("hourly", {}))
        if weather_frame.empty or air_frame.empty:
            raise WeatherDataError("历史训练数据为空")

        air_frame["date"] = pd.to_datetime(air_frame["time"]).dt.date.astype(str)
        daily_air = air_frame.groupby("date", as_index=False)["us_aqi"].mean()
        merged = weather_frame.merge(daily_air, on="date", how="left")
        merged["date"] = pd.to_datetime(merged["date"])
        merged["us_aqi"] = merged["us_aqi"].interpolate(limit_direction="both")
        return merged

    def get_china_current(self, locations):
        latitudes = ",".join(str(item.latitude) for item in locations)
        longitudes = ",".join(str(item.longitude) for item in locations)
        weather = self._get(
            self.FORECAST_URL,
            {
                "latitude": latitudes,
                "longitude": longitudes,
                "current": "temperature_2m,weather_code,wind_speed_10m",
                "timezone": "Asia/Shanghai",
            },
        )
        air = self._get(
            self.AIR_URL,
            {
                "latitude": latitudes,
                "longitude": longitudes,
                "current": "us_aqi,pm2_5",
                "timezone": "Asia/Shanghai",
            },
        )
        weather_items = weather if isinstance(weather, list) else [weather]
        air_items = air if isinstance(air, list) else [air]
        rows = []
        for index, location in enumerate(locations):
            weather_current = weather_items[index].get("current", {})
            air_current = air_items[index].get("current", {})
            rows.append(
                {
                    **location.to_dict(),
                    **weather_current,
                    "us_aqi": air_current.get("us_aqi"),
                    "pm2_5": air_current.get("pm2_5"),
                }
            )
        return rows
