import pandas as pd

from field_analytics import calculate_field_kpis, well_operational_summary


def sample_data():
    return pd.DataFrame([
        ["WELL-01", "2026-01-01", 100, 20, 1000, 80, 0],
        ["WELL-01", "2026-01-02", 90, 22, 980, 81, 1],
        ["WELL-02", "2026-01-01", 200, 10, 1100, 75, 0],
        ["WELL-02", "2026-01-02", 210, 11, 1110, 76, 0],
    ], columns=["Well_ID", "Date", "Oil_Rate", "Water_Cut", "Pressure", "Temperature", "Pump_Status"])


def test_field_kpis():
    kpis = calculate_field_kpis(sample_data())
    assert kpis["well_count"] == 2
    assert kpis["observation_count"] == 4
    assert kpis["total_oil"] == 600
    assert kpis["field_failure_rate"] == 0.25
    assert kpis["field_uptime"] == 0.75


def test_well_summary_keeps_wells_separate():
    summary = well_operational_summary(sample_data()).set_index("Well_ID")
    assert summary.loc["WELL-01", "Total_Oil"] == 190
    assert summary.loc["WELL-02", "Total_Oil"] == 410
    assert summary.loc["WELL-01", "Failure_Rate"] == 0.5
    assert summary.loc["WELL-02", "Failure_Rate"] == 0.0
