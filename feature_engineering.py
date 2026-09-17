"""Time-aware feature engineering for well sensor data."""

from __future__ import annotations

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = [
    "Well_ID", "Date", "Oil_Rate", "Water_Cut", "Pressure", "Temperature",
]
BASE_SENSOR_COLUMNS = ["Oil_Rate", "Water_Cut", "Pressure", "Temperature"]

FEATURE_COLS = [
    "Oil_Rate_Change_1D", "Oil_Rate_Change_3D", "Oil_Rate_Change_7D",
    "Pressure_Change_1D", "Pressure_Change_3D", "Pressure_Change_7D",
    "Oil_Rate_7D_Average", "Pressure_7D_Average", "Temperature_7D_Average",
    "Oil_Rate_7D_Std", "Pressure_7D_Std",
    "Oil_Rate_Decline_Rate", "Pressure_Decline_Rate", "Water_Cut_Trend",
]


def _safe_pct_change(current: pd.Series, previous: pd.Series) -> pd.Series:
    denominator = previous.replace(0, np.nan)
    return ((current - previous) / denominator) * 100.0


def _exact_calendar_lag(group: pd.DataFrame, column: str, days: int) -> pd.Series:
    """Return the value exactly N calendar days before each observation."""
    lookup = group.set_index("Date")[column]
    wanted_dates = group["Date"] - pd.Timedelta(days=days)
    values = lookup.reindex(wanted_dates)
    values.index = group.index
    return values


def _rolling_calendar_feature(group: pd.DataFrame, column: str, statistic: str) -> pd.Series:
    """Calculate a rolling calendar-time statistic using current/past data only."""
    indexed = group.set_index("Date")[column]
    # closed='both' gives the current observation and the preceding seven days.
    rolling = indexed.rolling("7D", closed="both", min_periods=1)
    values = getattr(rolling, statistic)()
    values = values.reindex(group["Date"])
    values.index = group.index
    return values


def _build_well_features(group: pd.DataFrame) -> pd.DataFrame:
    group = group.sort_values("Date").copy()

    for column in ["Oil_Rate", "Pressure"]:
        for days in (1, 3, 7):
            previous = _exact_calendar_lag(group, column, days)
            group[f"{column}_Change_{days}D"] = group[column] - previous

    group["Oil_Rate_7D_Average"] = _rolling_calendar_feature(group, "Oil_Rate", "mean")
    group["Pressure_7D_Average"] = _rolling_calendar_feature(group, "Pressure", "mean")
    group["Temperature_7D_Average"] = _rolling_calendar_feature(group, "Temperature", "mean")
    group["Oil_Rate_7D_Std"] = _rolling_calendar_feature(group, "Oil_Rate", "std")
    group["Pressure_7D_Std"] = _rolling_calendar_feature(group, "Pressure", "std")

    oil_previous = _exact_calendar_lag(group, "Oil_Rate", 7)
    pressure_previous = _exact_calendar_lag(group, "Pressure", 7)
    water_previous = _exact_calendar_lag(group, "Water_Cut", 7)
    group["Oil_Rate_Decline_Rate"] = _safe_pct_change(group["Oil_Rate"], oil_previous)
    group["Pressure_Decline_Rate"] = _safe_pct_change(group["Pressure"], pressure_previous)
    group["Water_Cut_Trend"] = group["Water_Cut"] - water_previous
    return group


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Return chronologically ordered well data with calendar-aware features.

    Lag features require an observation on the exact prior calendar date. This
    prevents a 30-day gap between data-collection periods from being treated as
    a one-day or seven-day change. Rolling features use only the current and
    preceding seven calendar days.
    """
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    result = df.copy()
    result["Date"] = pd.to_datetime(result["Date"], errors="raise")
    result = result.sort_values(["Well_ID", "Date"]).reset_index(drop=True)

    if result.duplicated(["Well_ID", "Date"]).any():
        raise ValueError("Feature engineering requires one observation per Well_ID and Date")

    well_frames = [
        _build_well_features(group)
        for _, group in result.groupby("Well_ID", sort=False)
    ]
    if well_frames:
        result = pd.concat(well_frames, ignore_index=True)
    return result.sort_values(["Well_ID", "Date"]).reset_index(drop=True)
