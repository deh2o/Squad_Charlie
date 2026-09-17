"""Future failure target construction for predictive maintenance."""

from __future__ import annotations

import pandas as pd


def add_failure_target(df: pd.DataFrame, horizon_days: int = 7) -> pd.DataFrame:
    """Add Failure_Next_7D using future calendar dates for each well.

    A target is only assigned when every one of the next ``horizon_days``
    calendar dates exists for that well. This prevents gaps between separate
    data collection periods from being mistaken for normal future operation.
    """
    if horizon_days < 1:
        raise ValueError("horizon_days must be at least 1")
    required = {"Well_ID", "Date", "Pump_Status"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    result = df.copy()
    result["Date"] = pd.to_datetime(result["Date"], errors="raise")
    result = result.sort_values(["Well_ID", "Date"]).reset_index(drop=True)
    result["Failure_Next_7D"] = pd.Series(pd.NA, index=result.index, dtype="Int64")

    for _, group in result.groupby("Well_ID", sort=False):
        group = group.sort_values("Date")
        indices = group.index.to_list()
        dates = group["Date"].to_list()
        statuses = group["Pump_Status"].astype(int).to_list()

        for position in range(len(indices) - horizon_days):
            current_date = dates[position]
            future_dates = dates[position + 1: position + horizon_days + 1]
            expected_dates = [
                current_date + pd.Timedelta(days=i)
                for i in range(1, horizon_days + 1)
            ]
            if future_dates != expected_dates:
                continue
            future_statuses = statuses[position + 1: position + horizon_days + 1]
            result.loc[indices[position], "Failure_Next_7D"] = int(max(future_statuses))

    return result
