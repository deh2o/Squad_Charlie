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
    """Return a fresh sqlite3 connection to the oilfield DB.

    A new connection per call rather than one shared global: sqlite3
    connections are not safe to reuse across threads, and the GUI may
    query from a worker thread while the main thread redraws.
    """
    return sqlite3.connect(DB_PATH)


def load_all_data() -> pd.DataFrame:
    """Load the entire production_data table."""
    conn = get_connection()
    try:
        # read_sql_query hands back a DataFrame directly, so no manual row loop.
        df = pd.read_sql_query("SELECT * FROM production_data", conn)
    finally:
        # try/finally so the connection closes even if the query raises.
        conn.close()
    return df


def load_well_data(well_id: str) -> pd.DataFrame:
    """Filter to a single well, sorted by date (essential for time-series charts)."""
    conn = get_connection()
    try:
        df = pd.read_sql_query(
            # ? placeholder instead of an f-string: prevents SQL injection.
            # ORDER BY Date is what makes the time-series charts come out
            # in chronological order and predict.py's iloc[-1] the latest day.
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