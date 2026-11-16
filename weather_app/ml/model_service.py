"""Train, evaluate, persist and run city-specific weather models."""

import hashlib
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, mean_absolute_error
from sklearn.pipeline import Pipeline

from weather_app.ml.features import (
    CONTEXT_COLUMNS,
    TARGET_COLUMNS,
    build_feature_frame,
    clean_training_frame,
)


class WeatherModelService:
    MODEL_VERSION = 2

    def __init__(self, weather_client, model_dir: Path, max_age_days=30, history_years=3):
        self.weather_client = weather_client
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.max_age_days = max_age_days
        self.history_years = history_years

    def _model_path(self, location):
        key = f"{location.name}:{location.latitude:.4f}:{location.longitude:.4f}"
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
        return self.model_dir / f"weather-{digest}.joblib"

    def _load_fresh_bundle(self, path):
        if not path.exists():
            return None
        age = datetime.now(timezone.utc) - datetime.fromtimestamp(
            path.stat().st_mtime, tz=timezone.utc
        )
        if age > timedelta(days=self.max_age_days):
            return None
        try:
            bundle = joblib.load(path)
            if bundle.get("version") == self.MODEL_VERSION:
                return bundle
        except (OSError, ValueError, EOFError, KeyError):
            return None
        return None

    def train_or_load(self, location, force=False):
        path = self._model_path(location)
        bundle = None if force else self._load_fresh_bundle(path)
        cache_hit = bundle is not None
        if bundle is None:
            frame = self.weather_client.get_training_frame(location, years=self.history_years)
            bundle = self.train(frame, location)
            temporary = path.with_suffix(".tmp")
            joblib.dump(bundle, temporary)
            os.replace(temporary, path)
        return bundle, cache_hit

    def train(self, raw_frame, location):
        clean = clean_training_frame(raw_frame)
        prepared, feature_columns = build_feature_frame(clean)
        prepared = prepared.dropna(subset=feature_columns + TARGET_COLUMNS + ["weather_group"])
        if len(prepared) < 90:
            raise ValueError("滞后特征处理后训练样本不足 90 天")

        split_index = max(60, int(len(prepared) * 0.8))
        split_index = min(split_index, len(prepared) - 30)
        train = prepared.iloc[:split_index]
        validation = prepared.iloc[split_index:]

        regressor = Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                (
                    "model",
                    RandomForestRegressor(
                        n_estimators=360,
                        min_samples_leaf=2,
                        max_features=0.8,
                        random_state=42,
                        n_jobs=-1,
                    ),
                ),
            ]
        )
        classifier = Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                (
                    "model",
                    RandomForestClassifier(
                        n_estimators=280,
                        min_samples_leaf=2,
                        class_weight="balanced_subsample",
                        random_state=42,
                        n_jobs=-1,
                    ),
                ),
            ]
        )

        regressor.fit(train[feature_columns], train[TARGET_COLUMNS])
        classifier.fit(train[feature_columns], train["weather_group"])
        validation_predictions = regressor.predict(validation[feature_columns])
        class_predictions = classifier.predict(validation[feature_columns])
        mae = mean_absolute_error(
            validation[TARGET_COLUMNS], validation_predictions, multioutput="raw_values"
        )
        accuracy = accuracy_score(validation["weather_group"], class_predictions)

        # Refit on all observations after the leakage-safe holdout evaluation.
        regressor.fit(prepared[feature_columns], prepared[TARGET_COLUMNS])
        classifier.fit(prepared[feature_columns], prepared["weather_group"])
        return {
            "version": self.MODEL_VERSION,
            "location": location.to_dict(),
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "training_start": clean["date"].min().date().isoformat(),
            "training_end": clean["date"].max().date().isoformat(),
            "training_samples": int(len(train)),
            "validation_samples": int(len(validation)),
            "feature_columns": feature_columns,
            "metrics": {
                "mae_high": round(float(mae[0]), 2),
                "mae_low": round(float(mae[1]), 2),
                "mae_aqi": round(float(mae[2]), 2),
                "weather_accuracy": round(float(accuracy), 3),
            },
            "regressor": regressor,
            "classifier": classifier,
            "history": clean,
        }

    def predict(self, bundle, days=7):
        history = bundle["history"].copy().sort_values("date")
        feature_columns = bundle["feature_columns"]
        regressor = bundle["regressor"]
        classifier = bundle["classifier"]
        metrics = bundle["metrics"]
        rows = []
        next_date = max(pd.Timestamp(date.today()), history["date"].max() + pd.Timedelta(days=1))

        for offset in range(days):
            prediction_date = next_date + pd.Timedelta(days=offset)
            context = {
                "date": prediction_date,
                "weather_code": history["weather_code"].iloc[-1],
                "precipitation_sum": float(history["precipitation_sum"].tail(7).mean()),
                "wind_speed_10m_max": float(history["wind_speed_10m_max"].tail(7).mean()),
                **{column: np.nan for column in TARGET_COLUMNS},
            }
            with_candidate = pd.concat([history, pd.DataFrame([context])], ignore_index=True)
            featured, _ = build_feature_frame(with_candidate)
            features = featured.iloc[[-1]][feature_columns]
            values = regressor.predict(features)[0]
            condition = str(classifier.predict(features)[0])

            high = round(float(max(values[0], values[1])), 1)
            low = round(float(min(values[0], values[1])), 1)
            aqi = round(float(max(values[2], 0)), 1)
            rows.append(
                {
                    "date": prediction_date.date().isoformat(),
                    "temperature_max": high,
                    "temperature_min": low,
                    "aqi": aqi,
                    "condition": condition,
                    "temperature_max_interval": [
                        round(high - metrics["mae_high"], 1),
                        round(high + metrics["mae_high"], 1),
                    ],
                    "temperature_min_interval": [
                        round(low - metrics["mae_low"], 1),
                        round(low + metrics["mae_low"], 1),
                    ],
                }
            )
            history = pd.concat(
                [
                    history,
                    pd.DataFrame(
                        [
                            {
                                **context,
                                "temperature_2m_max": high,
                                "temperature_2m_min": low,
                                "us_aqi": aqi,
                            }
                        ]
                    ),
                ],
                ignore_index=True,
            )

        return {
            "predictions": rows,
            "metrics": metrics,
            "model": {
                "algorithm": "RandomForestRegressor + RandomForestClassifier",
                "trained_at": bundle["trained_at"],
                "training_start": bundle["training_start"],
                "training_end": bundle["training_end"],
                "training_samples": bundle["training_samples"],
                "validation_samples": bundle["validation_samples"],
                "features": len(feature_columns),
            },
        }
