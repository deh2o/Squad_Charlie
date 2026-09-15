"""
data_loader.py
Member 1 (Data Engineer) | Tuesday deliverable.

The bridge between SQLite and every other module. train_model.py calls
load_all_data(), predict.py calls load_well_data(), the GUI calls
get_well_ids() to fill the well dropdown.
"""

import sqlite3
import pandas as pd

from config import DB_PATH


def get_connection():
    """Return a fresh sqlite3 connection to the oilfield DB."""
    return sqlite3.connect(DB_PATH)


def load_all_data() -> pd.DataFrame:
    """Load the entire production_data table."""
    conn = get_connection()
    try:
        df = pd.read_sql_query("SELECT * FROM production_data", conn)
    finally:
        conn.close()
    return df


def load_well_data(well_id: str) -> pd.DataFrame:
    """Filter to a single well, sorted by date (essential for time-series charts)."""
    conn = get_connection()
    try:
        df = pd.read_sql_query(
            "SELECT * FROM production_data WHERE Well_ID = ? ORDER BY Date",
            conn, params=(well_id,)
        )
    finally:
        conn.close()
    return df


def get_well_ids() -> list:
    """Return the sorted list of unique well IDs, for dropdown menus."""
    df = load_all_data()
    return sorted(df['Well_ID'].unique().tolist())


if __name__ == "__main__":
    # Quick smoke test
    ids = get_well_ids()
    print("Wells found:", ids)
    print(load_well_data(ids[0]).head())