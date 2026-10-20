from weather_app.ml.model_service import WeatherModelService
from weather_app.services.locations import DEFAULT_LOCATION


class FakeClient:
    pass


def test_model_trains_evaluates_and_predicts(tmp_path, weather_frame):
    service = WeatherModelService(FakeClient(), tmp_path)
    bundle = service.train(weather_frame, DEFAULT_LOCATION)
    result = service.predict(bundle, days=7)

    assert bundle["validation_samples"] >= 30
    assert bundle["metrics"]["mae_high"] >= 0
    assert 0 <= bundle["metrics"]["weather_accuracy"] <= 1
    assert len(result["predictions"]) == 7
    for row in result["predictions"]:
        assert row["temperature_max"] >= row["temperature_min"]
        assert row["aqi"] >= 0
        assert row["condition"] in {"晴", "多云", "雾", "雨", "雪", "雷暴"}
