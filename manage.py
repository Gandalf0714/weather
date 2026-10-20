"""Command-line utilities for running, training and exporting weather data."""

import argparse
from pathlib import Path

from waitress import serve

from weather_app import create_app
from weather_app.routes import get_model_service, get_weather_client, resolve_location


def train(city, force):
    app = create_app()
    with app.app_context():
        location = resolve_location(city)
        bundle, cache_hit = get_model_service().train_or_load(location, force=force)
        result = get_model_service().predict(bundle)
    print(f"城市: {location.name} ({location.province})")
    print(f"模型: {'缓存模型' if cache_hit else '新训练模型'}")
    print(f"训练区间: {bundle['training_start']} - {bundle['training_end']}")
    print(f"验证指标: {bundle['metrics']}")
    print("未来 7 天:")
    for item in result["predictions"]:
        print(
            f"  {item['date']}  {item['condition']:<4}  "
            f"{item['temperature_min']:>5.1f}~{item['temperature_max']:<5.1f} °C  "
            f"AQI {item['aqi']:>5.1f}"
        )


def export(city, output):
    app = create_app()
    with app.app_context():
        location = resolve_location(city)
        frame = get_weather_client().get_training_frame(
            location, years=app.config["HISTORY_YEARS"]
        )
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(destination, index=False, encoding="utf-8-sig")
    print(f"已导出 {len(frame)} 条记录到 {destination.resolve()}")


def build_parser():
    parser = argparse.ArgumentParser(description="观云台天气机器学习项目")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="启动生产 Web 服务")
    run_parser.add_argument("--host", default="127.0.0.1")
    run_parser.add_argument("--port", type=int, default=5000)

    train_parser = subparsers.add_parser("train", help="训练模型并打印 7 天预测")
    train_parser.add_argument("--city", default="南京")
    train_parser.add_argument("--force", action="store_true", help="忽略模型缓存并重新训练")

    export_parser = subparsers.add_parser("export", help="导出清洗后的历史训练数据")
    export_parser.add_argument("--city", default="南京")
    export_parser.add_argument("--output", default="data/weather_history.csv")
    return parser


def main():
    args = build_parser().parse_args()
    if args.command == "run":
        serve(create_app(), host=args.host, port=args.port)
    elif args.command == "train":
        train(args.city, args.force)
    elif args.command == "export":
        export(args.city, args.output)


if __name__ == "__main__":
    main()
