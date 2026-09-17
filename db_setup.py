"""
db_setup.py
Member 1 (Data Engineer) | Monday deliverable.

Creates the oilfield.db SQLite database and the production_data table,
matching the schema agreed in the project contract (Team_Charlie.pdf,
Section 2). Run this once before generate_data.py loads any rows.
"""

import os
import sqlite3

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS production_data (
    Well_ID      TEXT,        -- e.g. 'WELL-01'
    Date         TEXT,        -- 'YYYY-MM-DD' (stored as TEXT: SQLite has no native date type)
    Oil_Rate     REAL,        -- barrels per day
    Water_Cut    REAL,        -- percentage 0-100
    Pressure     REAL,        -- psi
    Temperature  REAL,        -- degrees Celsius
    Pump_Status  INTEGER,     -- 0 = Normal, 1 = Failure (the ML target)
    UNIQUE (Well_ID, Date)    -- one reading per well per day: makes CSV loads idempotent
);
"""

# Older databases were created without the UNIQUE constraint; the index gives
# them the same guarantee without dropping their rows.
UNIQUE_INDEX = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_well_date
    ON production_data (Well_ID, Date);
"""

DEDUPE = """
DELETE FROM production_data
WHERE rowid NOT IN (
    SELECT MIN(rowid) FROM production_data GROUP BY Well_ID, Date
);
"""


def create_database():
    """Create data/oilfield.db and the production_data table if missing.

    Safe to run repeatedly: the table is only created when absent, any
    duplicates left by pre-constraint loads are removed, and the unique
    index is only added once.
    """
    # Make sure the data/ folder exists before sqlite3 tries to create the file in it
    os.makedirs(os.path.dirname(config.DB_PATH) or ".", exist_ok=True)

    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()
    cursor.execute(SCHEMA)
    # Dedupe before indexing: CREATE UNIQUE INDEX fails if duplicates exist.
    cursor.execute(DEDUPE)
    removed = cursor.rowcount
    cursor.execute(UNIQUE_INDEX)
    conn.commit()
    conn.close()

    if removed:
        print(f"Removed {removed} duplicate row(s) from earlier loads")
    print(f"Database ready at {config.DB_PATH}")


if __name__ == "__main__":
    create_database()