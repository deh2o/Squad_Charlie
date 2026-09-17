import pandas as pd

from feature_engineering import FEATURE_COLS, add_features
from predictive_target import add_failure_target


def test_features_are_created_per_well_without_cross_well_leakage():
    df = pd.DataFrame([
        {"Well_ID": "WELL-01", "Date": "2026-01-01", "Oil_Rate": 100, "Water_Cut": 10, "Pressure": 1000, "Temperature": 70, "Pump_Status": 0},
        {"Well_ID": "WELL-01", "Date": "2026-01-02", "Oil_Rate": 90, "Water_Cut": 11, "Pressure": 990, "Temperature": 71, "Pump_Status": 0},
        {"Well_ID": "WELL-02", "Date": "2026-01-01", "Oil_Rate": 500, "Water_Cut": 20, "Pressure": 2000, "Temperature": 80, "Pump_Status": 0},
        {"Well_ID": "WELL-02", "Date": "2026-01-02", "Oil_Rate": 490, "Water_Cut": 21, "Pressure": 1990, "Temperature": 81, "Pump_Status": 0},
    ])
    out = add_features(df)
    first_well_second_day = out[(out.Well_ID == "WELL-01") & (out.Date == pd.Timestamp("2026-01-02"))].iloc[0]
    assert first_well_second_day["Oil_Rate_Change_1D"] == -10
    assert first_well_second_day["Pressure_Change_1D"] == -10

    first_well = out[out.Well_ID == "WELL-01"].iloc[0]
    assert pd.isna(first_well["Oil_Rate_Change_1D"])


def test_feature_columns_exist_and_data_is_chronological():
    df = pd.DataFrame([
        {"Well_ID": "WELL-01", "Date": "2026-01-03", "Oil_Rate": 80, "Water_Cut": 10, "Pressure": 980, "Temperature": 70},
        {"Well_ID": "WELL-01", "Date": "2026-01-01", "Oil_Rate": 100, "Water_Cut": 10, "Pressure": 1000, "Temperature": 70},
        {"Well_ID": "WELL-01", "Date": "2026-01-02", "Oil_Rate": 90, "Water_Cut": 10, "Pressure": 990, "Temperature": 70},
    ])
    out = add_features(df)
    assert all(column in out.columns for column in FEATURE_COLS)
    assert out["Date"].tolist() == sorted(out["Date"].tolist())


def test_future_target_does_not_count_current_failure():
    rows = []
    for day in range(10):
        rows.append({
            "Well_ID": "WELL-01", "Date": f"2026-01-{day + 1:02d}",
            "Oil_Rate": 100, "Water_Cut": 10, "Pressure": 1000,
            "Temperature": 70, "Pump_Status": 1 if day == 0 else 0,
        })
    out = add_failure_target(pd.DataFrame(rows))
    assert out.loc[0, "Failure_Next_7D"] == 0
    assert out.loc[1, "Failure_Next_7D"] == 0
    assert pd.isna(out.loc[3, "Failure_Next_7D"])


def test_calendar_lag_does_not_cross_data_gap():
    df = pd.DataFrame([
        {"Well_ID": "WELL-01", "Date": "2026-01-01", "Oil_Rate": 100, "Water_Cut": 10, "Pressure": 2000, "Temperature": 80},
        {"Well_ID": "WELL-01", "Date": "2026-01-02", "Oil_Rate": 110, "Water_Cut": 11, "Pressure": 1990, "Temperature": 81},
        {"Well_ID": "WELL-01", "Date": "2026-02-01", "Oil_Rate": 300, "Water_Cut": 30, "Pressure": 2500, "Temperature": 90},
    ])
    out = add_features(df)
    last = out.iloc[-1]
    assert pd.isna(last["Oil_Rate_Change_1D"])
    assert pd.isna(last["Oil_Rate_Change_7D"])


def test_calendar_lag_uses_exact_date():
    df = pd.DataFrame([
        {"Well_ID": "WELL-01", "Date": "2026-01-01", "Oil_Rate": 100, "Water_Cut": 10, "Pressure": 2000, "Temperature": 80},
        {"Well_ID": "WELL-01", "Date": "2026-01-02", "Oil_Rate": 110, "Water_Cut": 11, "Pressure": 1990, "Temperature": 81},
        {"Well_ID": "WELL-01", "Date": "2026-01-09", "Oil_Rate": 150, "Water_Cut": 15, "Pressure": 1950, "Temperature": 82},
    ])
    out = add_features(df)
    assert out.iloc[1]["Oil_Rate_Change_1D"] == 10
    assert out.iloc[2]["Oil_Rate_Change_7D"] == 40
