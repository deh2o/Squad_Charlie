"""
predict.py
Member 2 (ML Engineer) | Tuesday deliverable.

The function the GUI calls when "Run Diagnostics" is clicked. Turns the
latest sensor reading for a well into a failure probability, and labels
that probability NORMAL / WARNING / CRITICAL for display.
"""

import os

import joblib

from data_loader import load_well_data, get_well_ids
from config import MODEL_PATH, RISK_THRESHOLD, WARNING_THRESHOLD

# Must match FEATURE_COLS in train_model.py, in the same order.
FEATURES = ['Oil_Rate', 'Water_Cut', 'Pressure', 'Temperature']

_model = None  # populated on first use and then reused


def get_model():
    """Load the trained model once and cache it.

    Reading the .pkl on every click would freeze the GUI for seconds, and
    loading it at import time would make the whole app fail to start when
    the model has not been trained yet.
    """
    global _model
    if _model is None:
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(
                f"No trained model at {MODEL_PATH}. Run train_model.py first."
            )
        _model = joblib.load(MODEL_PATH)
    return _model


def predict_failure_risk(well_id: str) -> float:
    """Return failure risk score 0.0-1.0 for the most recent day of a well."""
    df = load_well_data(well_id)

    if df.empty:
        raise ValueError(f"No data for {well_id}")

    # Rows arrive sorted by date, so the last one is the most recent reading.
    # Double brackets keep it a 1-row DataFrame: sklearn requires 2D input.
    latest = df.iloc[[-1]]
    X = latest[FEATURES]

    risk_score = get_model().predict_proba(X)[0, 1]  # [0,1] = P(failure) for this one row
    return float(risk_score)


def get_risk_level(score: float) -> str:
    """Human-readable risk label."""
    if score >= RISK_THRESHOLD:
        return "CRITICAL"
    elif score >= WARNING_THRESHOLD:
        return "WARNING"
    else:
        return "NORMAL"


def check_all_wells() -> dict:
    """Score every well — used for auto-alerts / a full-field overview."""
    results = {}
    for well in get_well_ids():
        score = predict_failure_risk(well)
        results[well] = {'score': score, 'level': get_risk_level(score)}
    return results


if __name__ == "__main__":
    for well, info in check_all_wells().items():
        print(f"{well}: {info['score'] * 100:.1f}%  [{info['level']}]")
