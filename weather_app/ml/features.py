"""Leakage-safe feature engineering for daily weather time series."""

import numpy as np
import pandas as pd


TARGET_COLUMNS = ["temperature_2m_max", "temperature_2m_min", "us_aqi"]
CONTEXT_COLUMNS = TARGET_COLUMNS + ["precipitation_sum", "wind_speed_10m_max"]
CALENDAR_COLUMNS = ["doy_sin", "doy_cos", "month_sin", "month_cos", "year_offset"]
LAG_WINDOWS = (1, 7)


def weather_group(code):
    """Collapse WMO weather codes into useful prediction classes."""
    code = int(code)
    if code == 0:
        return "晴"
    if code <= 3:
        return "多云"
    if code in (45, 48):
        return "雾"
    if 51 <= code <= 67 or 80 <= code <= 82:
        return "雨"
    if 71 <= code <= 77 or code in (85, 86):
        return "雪"
    if code >= 95:
        return "雷暴"
    return "多云"


def clean_training_frame(frame):
    required = {"date", "weather_code", *CONTEXT_COLUMNS}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"训练数据缺少字段: {', '.join(sorted(missing))}")

    cleaned = frame.copy().sort_values("date").drop_duplicates("date")
    cleaned["date"] = pd.to_datetime(cleaned["date"])
    for column in ["weather_code", *CONTEXT_COLUMNS]:
        cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce")
    cleaned[TARGET_COLUMNS] = cleaned[TARGET_COLUMNS].interpolate(limit_direction="both")
    cleaned["precipitation_sum"] = cleaned["precipitation_sum"].fillna(0)
    cleaned["wind_speed_10m_max"] = cleaned["wind_speed_10m_max"].interpolate(
        limit_direction="both"
    )
    cleaned = cleaned.dropna(subset=["date", "weather_code", *TARGET_COLUMNS])
    if len(cleaned) < 120:
        raise ValueError("至少需要 120 天的有效历史数据才能训练模型")
    return cleaned.reset_index(drop=True)


def build_feature_frame(frame):
    """Build calendar and shifted rolling features without future leakage."""
    data = frame.copy()
    dates = pd.to_datetime(data["date"])
    day_of_year = dates.dt.dayofyear
    month = dates.dt.month
    data["doy_sin"] = np.sin(2 * np.pi * day_of_year / 365.25)
    data["doy_cos"] = np.cos(2 * np.pi * day_of_year / 365.25)
    data["month_sin"] = np.sin(2 * np.pi * month / 12)
    data["month_cos"] = np.cos(2 * np.pi * month / 12)
    data["year_offset"] = dates.dt.year - dates.dt.year.min()

    feature_columns = list(CALENDAR_COLUMNS)
    for column in CONTEXT_COLUMNS:
        shifted = data[column].shift(1)
        for lag in LAG_WINDOWS:
            feature_name = f"{column}_lag_{lag}"
            data[feature_name] = data[column].shift(lag)
            feature_columns.append(feature_name)
        for window in (7, 30):
            feature_name = f"{column}_mean_{window}"
            data[feature_name] = shifted.rolling(window, min_periods=max(3, window // 3)).mean()
            feature_columns.append(feature_name)

    data["weather_group"] = data["weather_code"].map(weather_group)
    return data, feature_columns
