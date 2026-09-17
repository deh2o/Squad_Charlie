import pandas as pd

import train_model
from feature_engineering import FEATURE_COLS


def _make_history(days=60):
    rows = []
    for well_num in range(1, 4):
        for day in range(days):
            failure = 1 if day in {20 + well_num, 45 + well_num} else 0
            rows.append({
                "Well_ID": f"WELL-{well_num:02d}",
                "Date": (pd.Timestamp("2026-01-01") + pd.Timedelta(days=day)).strftime("%Y-%m-%d"),
                "Oil_Rate": 200 - day * 0.5 - failure * 70,
                "Water_Cut": 10 + day * 0.1,
                "Pressure": 2500 - day * 2 - failure * 400,
                "Temperature": 80 + day * 0.05,
                "Pump_Status": failure,
            })
    return pd.DataFrame(rows)


def test_prepare_training_data_builds_future_target(monkeypatch):
    df = _make_history()
    out = train_model.prepare_training_data(df)
    assert set(FEATURE_COLS).issubset(out.columns)
    assert "Failure_Next_7D" in out.columns
    assert out["Failure_Next_7D"].isin([0, 1]).all()
    assert out["Failure_Next_7D"].nunique() == 2


def test_time_split_keeps_test_dates_after_training_dates():
    df = train_model.prepare_training_data(_make_history())
    train, test, cutoff = train_model._time_split(df)
    assert train["Date"].max() < cutoff
    assert test["Date"].min() >= cutoff
    assert train["Date"].max() < test["Date"].min()
