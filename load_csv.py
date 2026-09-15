"""
load_csv.py
Member 1 (Data Engineer) | Monday deliverable.

Step 2 of the data pipeline: read the CSV produced by generate_data.py
and load it into the production_data table. Re-running is safe — rows
are keyed on (Well_ID, Date), so an already-loaded reading is skipped
instead of duplicated.

Run order: db_setup.py -> generate_data.py -> load_csv.py
"""

import csv
import os
import sqlite3

from config import DB_PATH, CSV_PATH
from logger import log_database_event, log_system_error

EXPECTED_COLUMNS = 7  # Well_ID, Date, Oil_Rate, Water_Cut, Pressure, Temperature, Pump_Status

# OR IGNORE relies on the UNIQUE (Well_ID, Date) constraint from db_setup.py:
# a reading already in the table is silently skipped instead of duplicated.
INSERT_SQL = """
    INSERT OR IGNORE INTO production_data
    (Well_ID, Date, Oil_Rate, Water_Cut, Pressure, Temperature, Pump_Status)
    VALUES (?, ?, ?, ?, ?, ?, ?)
"""


def load_csv_into_db(csv_path=CSV_PATH):
    """Load CSV rows into production_data, skipping rows already present.

    Args:
        csv_path: Path to the CSV file to load. Defaults to config.CSV_PATH.

    Returns:
        Number of rows inserted into the database.
    """
    log_database_event('load_start', f'Loading CSV from {csv_path}')

    if not os.path.exists(csv_path):
        error_msg = f"CSV file not found: {csv_path}"
        log_database_event('file_not_found', error_msg, 'error')
        log_system_error('csv_file_error', error_msg)
        raise FileNotFoundError(error_msg)

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        inserted = skipped = malformed = 0

        with open(csv_path, newline='') as f:
            reader = csv.reader(f)
            next(reader)  # skip header row

            for row in reader:
                # csv.reader yields plain strings; SQLite converts them to REAL /
                # INTEGER automatically because of the column types in the schema.
                # A short or long row would silently shift columns, so drop it.
                if len(row) != EXPECTED_COLUMNS:
                    log_database_event('malformed_row', f'Skipping row: {row}', 'warning')
                    malformed += 1
                    continue

                cursor.execute(INSERT_SQL, row)
                if cursor.rowcount:  # 0 when the (Well_ID, Date) pair already exists
                    inserted += 1
                else:
                    skipped += 1

        conn.commit()
        conn.close()

        result_msg = f"Loaded '{csv_path}' into {DB_PATH}: {inserted} inserted, {skipped} already present, {malformed} malformed"
        print(result_msg)
        log_database_event('load_complete', result_msg)
        return inserted

    except Exception as error:
        error_msg = f"Failed to load CSV: {error}"
        log_database_event('load_failed', error_msg, 'error')
        log_system_error('csv_load_error', error_msg, error)
        raise


if __name__ == "__main__":
    load_csv_into_db()
