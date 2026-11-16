"""HTTP routes for the dashboard and machine-learning APIs."""

from flask import Blueprint, current_app, jsonify, render_template, request

from weather_app.ml.model_service import WeatherModelService
from weather_app.services.locations import CAPITALS, DEFAULT_LOCATION, LOCATION_INDEX, find_preset
from weather_app.services.weather_client import WeatherClient, WeatherDataError


api = Blueprint("api", __name__)


def get_weather_client():
    if "weather_client" not in current_app.extensions:
        current_app.extensions["weather_client"] = WeatherClient(
            current_app.config["CACHE_DIR"],
            timeout=current_app.config["HTTP_TIMEOUT"],
            ttl_seconds=current_app.config["CACHE_TTL_SECONDS"],
        )
    return current_app.extensions["weather_client"]


def get_model_service():
    if "model_service" not in current_app.extensions:
        current_app.extensions["model_service"] = WeatherModelService(
            get_weather_client(),
            current_app.config["MODEL_DIR"],
            max_age_days=current_app.config["MODEL_MAX_AGE_DAYS"],
            history_years=current_app.config["HISTORY_YEARS"],
        )
    return current_app.extensions["model_service"]


def resolve_location(city):
    city = (city or DEFAULT_LOCATION.name).strip()
    if city in LOCATION_INDEX:
        return LOCATION_INDEX[city]
    matches = get_weather_client().search_locations(city, count=1)
    if not matches:
        raise ValueError(f"未找到城市: {city}")
    return matches[0]


@api.get("/")
def index():
    return render_template("index.html")


@api.get("/api/health")
def health():
    return jsonify({"status": "ok", "project": "Weather ML"})


@api.get("/api/locations")
def locations():
    query = request.args.get("q", "").strip()
    matches = find_preset(query)
    if query and not matches:
        matches = get_weather_client().search_locations(query)
    return jsonify({"locations": [item.to_dict() for item in matches[:8]]})


@api.get("/api/weather")
def weather():
    location = resolve_location(request.args.get("city"))
    return jsonify(get_weather_client().get_dashboard(location))


@api.route("/api/predict", methods=["GET", "POST"])
def predict():
    payload = request.get_json(silent=True) or {}
    city = payload.get("city") or request.args.get("city")
    force = bool(payload.get("retrain")) or request.args.get("retrain") == "1"
    location = resolve_location(city)
    bundle, cache_hit = get_model_service().train_or_load(location, force=force)
    result = get_model_service().predict(bundle, days=7)
    result.update(
        {
            "location": location.to_dict(),
            "cached_model": cache_hit,
            "source": "Open-Meteo 历史数据 + 本地 scikit-learn 模型",
        }
    )
    return jsonify(result)


@api.get("/api/china")
def china():
    rows = get_weather_client().get_china_current(CAPITALS)
    return jsonify({"locations": rows, "source": "Open-Meteo"})


@api.errorhandler(WeatherDataError)
def handle_weather_error(error):
    return jsonify({"error": str(error), "type": "upstream_error"}), 502


@api.errorhandler(ValueError)
def handle_value_error(error):
    return jsonify({"error": str(error), "type": "validation_error"}), 400


@api.app_errorhandler(404)
def handle_not_found(_error):
    if request.path.startswith("/api/"):
        return jsonify({"error": "接口不存在", "type": "not_found"}), 404
    return render_template("index.html"), 404
