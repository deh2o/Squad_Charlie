"""Data access layer for SQLite and the project's raw historical CSV files."""

import glob
import os
import sqlite3
import pandas as pd

import config
from validation import EXPECTED_COLUMNS, validate_row


def get_connection():
    """Return a fresh SQLite connection."""
    return sqlite3.connect(config.DB_PATH)


def load_all_data() -> pd.DataFrame:
    """Load the entire production_data table."""
    conn = get_connection()
    try:
        return pd.read_sql_query("SELECT * FROM production_data", conn)
    finally:
        conn.close()


def load_well_data(well_id: str) -> pd.DataFrame:
    """Load one well, sorted chronologically."""
    conn = get_connection()
    try:
        return pd.read_sql_query(
            "SELECT * FROM production_data WHERE Well_ID = ? ORDER BY Date",
            conn, params=(well_id,)
        )
    finally:
        conn.close()


def load_raw_history() -> pd.DataFrame:
    """Load all valid raw CSVs and consolidate duplicate well/date readings.

    Raw files can represent separate collection batches and may overlap. Since
    the database contract permits one reading per well/day, overlapping rows
    are consolidated by averaging sensor values and treating any failure in
    the duplicate observations as a failure (max Pump_Status).
    """
    paths = sorted(glob.glob(os.path.join(config.RAW_DATA_DIR, "*.csv")))
    if not paths:
        return pd.DataFrame(columns=EXPECTED_COLUMNS)

    frames = []
    for path in paths:
        rows = []
        with open(path, newline="", encoding="utf-8-sig") as file:
            import csv
            reader = csv.reader(file)
            header = next(reader, None)
            if header != EXPECTED_COLUMNS:
                raise ValueError(f"Invalid CSV header in {path}. Expected {EXPECTED_COLUMNS}, got {header}")
            for line_number, row in enumerate(reader, start=2):
                if validate_row(row):
                    continue
                rows.append({
                    "Well_ID": row[0].strip(),
                    "Date": row[1].strip(),
                    "Oil_Rate": float(row[2]),
                    "Water_Cut": float(row[3]),
                    "Pressure": float(row[4]),
                    "Temperature": float(row[5]),
                    "Pump_Status": int(row[6]),
                })
        if rows:
            frames.append(pd.DataFrame(rows))

    if not frames:
        return pd.DataFrame(columns=EXPECTED_COLUMNS)

    combined = pd.concat(frames, ignore_index=True)
    combined["Date"] = pd.to_datetime(combined["Date"], errors="raise")
    combined = (
        combined.groupby(["Well_ID", "Date"], as_index=False)
        .agg({
            "Oil_Rate": "mean",
            "Water_Cut": "mean",
            "Pressure": "mean",
            "Temperature": "mean",
            "Pump_Status": "max",
        })
        .sort_values(["Well_ID", "Date"])
        .reset_index(drop=True)
    )
    combined["Date"] = combined["Date"].dt.strftime("%Y-%m-%d")
    return combined


def get_well_ids() -> list:
    """Return sorted unique well IDs from SQLite."""
    df = load_all_data()
    return sorted(df["Well_ID"].unique().tolist())


if __name__ == "__main__":
    print("Database wells:", get_well_ids())
    raw = load_raw_history()
    print(f"Raw historical rows after consolidation: {len(raw)}")
