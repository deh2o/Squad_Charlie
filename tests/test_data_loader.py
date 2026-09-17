import pandas as pd

import data_loader


def test_load_raw_history_consolidates_overlapping_dates(monkeypatch, tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    header = "Well_ID,Date,Oil_Rate,Water_Cut,Pressure,Temperature,Pump_Status\n"
    (raw / "a.csv").write_text(header + "WELL-01,2026-01-01,100,20,2000,80,0\n")
    (raw / "b.csv").write_text(header + "WELL-01,2026-01-01,200,40,2200,100,1\n")
    monkeypatch.setattr(data_loader.config, "RAW_DATA_DIR", str(raw))

    df = data_loader.load_raw_history()
    row = df.iloc[0]
    assert len(df) == 1
    assert row["Oil_Rate"] == 150
    assert row["Pressure"] == 2100
    assert row["Pump_Status"] == 1
