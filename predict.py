"""Generate 7-day pump-failure risk and local explanations."""

from __future__ import annotations

import os

import joblib
import pandas as pd

import config
from data_loader import load_well_data, get_well_ids
from explainability import explain_prediction
from feature_engineering import add_features

_model = None


def get_model():
    global _model
    if _model is None:
        if not os.path.exists(config.MODEL_PATH):
            raise FileNotFoundError(f"No trained model at {config.MODEL_PATH}. Run train_model.py first.")
        artifact = joblib.load(config.MODEL_PATH)
        if isinstance(artifact, dict) and "model" in artifact:
            _model = artifact
        else:
            _model = {"model": artifact, "feature_cols": ["Oil_Rate", "Water_Cut", "Pressure", "Temperature"], "target": "Pump_Status"}
    return _model


def _latest_prediction_row(well_id: str):
    df = load_well_data(well_id)
    if df.empty:
        raise ValueError(f"No data for {well_id}")

    artifact = get_model()
    if artifact.get("target") != "Failure_Next_7D":
        raise ValueError("The installed model is an older same-day model. Retrain with train_model.py.")

    featured = add_features(df)
    feature_cols = artifact["feature_cols"]
    usable = featured.dropna(subset=feature_cols)
    if usable.empty:
        raise ValueError(f"Not enough historical data to calculate features for {well_id}")
    return artifact, usable.iloc[[-1]], feature_cols


def predict_failure_risk(well_id: str) -> float:
    artifact, latest, feature_cols = _latest_prediction_row(well_id)
    return float(artifact["model"].predict_proba(latest[feature_cols])[0, 1])


def get_prediction_details(well_id: str, top_n: int = 5) -> dict:
    """Return risk, level, and the strongest local feature signals."""
    artifact, latest, feature_cols = _latest_prediction_row(well_id)
    model = artifact["model"]
    score = float(model.predict_proba(latest[feature_cols])[0, 1])

    baseline_values = artifact.get("feature_baseline")
    baseline = pd.Series(baseline_values, dtype=float) if baseline_values else None
    drivers = explain_prediction(model, latest, feature_cols, baseline=baseline, top_n=top_n)

    return {
        "well_id": well_id,
        "score": score,
        "level": get_risk_level(score),
        "drivers": drivers,
        "as_of": str(latest["Date"].iloc[0].date()),
    }


def get_risk_level(score: float) -> str:
    if score >= config.RISK_THRESHOLD:
        return "CRITICAL"
    if score >= config.WARNING_THRESHOLD:
        return "WARNING"
    return "NORMAL"


def check_all_wells() -> dict:
    results = {}
    for well in get_well_ids():
        details = get_prediction_details(well)
        results[well] = details
    return results


if __name__ == "__main__":
    for well, info in check_all_wells().items():
        print(f"{well}: {info['score'] * 100:.1f}%  [{info['level']}]")
        for driver in info["drivers"][:3]:
            print(f"  - {driver['name']}: {driver['direction']} ({driver['contribution']:+.3f})")
