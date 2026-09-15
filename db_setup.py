"""
db_setup.py
Member 1 (Data Engineer) | Monday deliverable.

Creates the oilfield.db SQLite database and the production_data table,
matching the schema agreed in the project contract (Team_Charlie.pdf,
Section 2). Run this once before generate_data.py loads any rows.
"""

import os
import sqlite3

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS production_data (
    Well_ID      TEXT,        -- e.g. 'WELL-01'
    Date         TEXT,        -- 'YYYY-MM-DD' (stored as TEXT: SQLite has no native date type)
    Oil_Rate     REAL,        -- barrels per day
    Water_Cut    REAL,        -- percentage 0-100
    Pressure     REAL,        -- psi
    Temperature  REAL,        -- degrees Celsius
    Pump_Status  INTEGER      -- 0 = Normal, 1 = Failure (the ML target)
);
"""


def create_database():
    """Create data/oilfield.db and the production_data table if missing."""
    # Make sure the data/ folder exists before sqlite3 tries to create the file in it
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(SCHEMA)
    conn.commit()
    conn.close()
    print(f"Database ready at {DB_PATH}")


if __name__ == "__main__":
    create_database()