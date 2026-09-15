"""
predict.py
Member 2 (ML Engineer) | Tuesday deliverable.

The function the GUI calls when "Run Diagnostics" is clicked. Loads
the trained model ONCE at import time (loading a .pkl on every click
would freeze the GUI for seconds — see app.py).
"""

import joblib

from data_loader import load_well_data, get_well_ids
from config import MODEL_PATH, RISK_THRESHOLD

_model = joblib.load(MODEL_PATH)  # loaded once at module level

FEATURES = ['Oil_Rate', 'Water_Cut', 'Pressure', 'Temperature']


def predict_failure_risk(well_id: str) -> float:
    """Return failure risk score 0.0-1.0 for the most recent day of a well."""
    df = load_well_data(well_id)

    if df.empty:
        raise ValueError(f"No data for {well_id}")

    latest = df.iloc[[-1]]  # double brackets: keeps it a DataFrame (2D), sklearn needs 2D
    X = latest[FEATURES]

    risk_score = _model.predict_proba(X)[0, 1]  # [0,1] = P(failure) for this one row
    return float(risk_score)


def get_risk_level(score: float) -> str:
    """Human-readable risk label."""
    if score >= RISK_THRESHOLD:
        return "CRITICAL"
    elif score >= 0.50:
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
