from weather_app.ml.features import build_feature_frame, clean_training_frame, weather_group


def test_weather_group_covers_core_wmo_codes():
    assert weather_group(0) == "晴"
    assert weather_group(3) == "多云"
    assert weather_group(63) == "雨"
    assert weather_group(75) == "雪"
    assert weather_group(95) == "雷暴"


def test_feature_lags_only_use_past_values(weather_frame):
    clean = clean_training_frame(weather_frame)
    featured, columns = build_feature_frame(clean)
    row = featured.iloc[40]
    assert row["temperature_2m_max_lag_1"] == clean.iloc[39]["temperature_2m_max"]
    assert row["temperature_2m_max_lag_7"] == clean.iloc[33]["temperature_2m_max"]
    assert "temperature_2m_max" not in columns


def test_clean_training_frame_rejects_too_little_data(weather_frame):
    try:
        clean_training_frame(weather_frame.head(40))
    except ValueError as error:
        assert "120" in str(error)
    else:
        raise AssertionError("expected too-small training data to be rejected")
