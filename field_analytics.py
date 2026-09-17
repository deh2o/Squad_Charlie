"""Field-level analytics for the digital oilfield dashboard.

Keeps operational KPIs separate from ML predictions so the dashboard can
show what is measured historically versus what the model predicts.
"""
from __future__ import annotations

import pandas as pd

from data_loader import load_all_data
from predict import get_prediction_details


def _empty_summary() -> dict:
    return {
        "well_count": 0,
        "observation_count": 0,
        "total_oil": 0.0,
        "average_daily_oil": 0.0,
        "field_failure_rate": 0.0,
        "field_uptime": 1.0,
        "average_water_cut": 0.0,
        "average_pressure": 0.0,
        "average_temperature": 0.0,
        "risk_counts": {"NORMAL": 0, "WARNING": 0, "CRITICAL": 0},
        "average_failure_risk": 0.0,
        "data_quality_score": 100.0,
    }


def calculate_field_kpis(df: pd.DataFrame) -> dict:
    """Calculate field KPIs from the supplied production observations."""
    if df.empty:
        return _empty_summary()

    failures = int(df["Pump_Status"].sum())
    observations = len(df)
    return {
        "well_count": int(df["Well_ID"].nunique()),
        "observation_count": observations,
        "total_oil": float(df["Oil_Rate"].sum()),
        "average_daily_oil": float(df.groupby("Date")["Oil_Rate"].sum().mean()),
        "field_failure_rate": failures / observations,
        "field_uptime": (observations - failures) / observations,
        "average_water_cut": float(df["Water_Cut"].mean()),
        "average_pressure": float(df["Pressure"].mean()),
        "average_temperature": float(df["Temperature"].mean()),
        "risk_counts": {"NORMAL": 0, "WARNING": 0, "CRITICAL": 0},
        "average_failure_risk": 0.0,
        "data_quality_score": 100.0,
    }


def get_field_risk() -> dict:
    """Return model risk details for every well, isolated from historical KPIs."""
    results = []
    for well_id in sorted(load_all_data()["Well_ID"].unique()):
        try:
            details = get_prediction_details(well_id)
        except (ValueError, FileNotFoundError):
            continue
        results.append(details)

    counts = {"NORMAL": 0, "WARNING": 0, "CRITICAL": 0}
    for item in results:
        counts[item["level"]] = counts.get(item["level"], 0) + 1

    return {
        "wells": results,
        "risk_counts": counts,
        "average_failure_risk": (
            sum(item["score"] for item in results) / len(results) if results else 0.0
        ),
    }


def build_field_snapshot(df: pd.DataFrame | None = None) -> dict:
    """Build one dashboard-ready field snapshot."""
    if df is None:
        df = load_all_data()
    kpis = calculate_field_kpis(df)
    risk = get_field_risk() if not df.empty else {"wells": [], "risk_counts": kpis["risk_counts"], "average_failure_risk": 0.0}
    kpis["risk_counts"] = risk["risk_counts"]
    kpis["average_failure_risk"] = risk["average_failure_risk"]
    return {"kpis": kpis, "risk": risk}


def well_operational_summary(df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Return one row per well with measured operational KPIs."""
    if df is None:
        df = load_all_data()
    if df.empty:
        return pd.DataFrame(columns=["Well_ID", "Total_Oil", "Avg_Oil_Rate", "Avg_Water_Cut", "Avg_Pressure", "Failure_Rate", "Uptime"])

    grouped = df.groupby("Well_ID")
    out = grouped.agg(
        Total_Oil=("Oil_Rate", "sum"),
        Avg_Oil_Rate=("Oil_Rate", "mean"),
        Avg_Water_Cut=("Water_Cut", "mean"),
        Avg_Pressure=("Pressure", "mean"),
        Failure_Rate=("Pump_Status", "mean"),
    ).reset_index()
    out["Uptime"] = 1.0 - out["Failure_Rate"]
    return out
