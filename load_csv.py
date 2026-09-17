"""Validate and load production CSV rows into SQLite."""
import csv
import os
import sqlite3

import config
from logger import log_database_event, log_system_error
from validation import EXPECTED_COLUMNS, validate_row

EXPECTED_COLUMN_COUNT = len(EXPECTED_COLUMNS)
INSERT_SQL = """
    INSERT OR IGNORE INTO production_data
    (Well_ID, Date, Oil_Rate, Water_Cut, Pressure, Temperature, Pump_Status)
    VALUES (?, ?, ?, ?, ?, ?, ?)
"""


def _normalise_row(row):
    return (
        row[0].strip(), row[1].strip(), float(row[2]), float(row[3]),
        float(row[4]), float(row[5]), int(row[6]),
    )


def load_csv_into_db(csv_path=None, return_report=False):
    if csv_path is None:
        csv_path = config.CSV_PATH
    log_database_event('load_start', f'Loading CSV from {csv_path}')
    if not os.path.exists(csv_path):
        error_msg = f"CSV file not found: {csv_path}"
        log_database_event('file_not_found', error_msg, 'error')
        log_system_error('csv_file_error', error_msg)
        raise FileNotFoundError(error_msg)

    conn = None
    total = inserted = skipped = rejected = malformed = 0
    errors = []
    try:
        conn = sqlite3.connect(config.DB_PATH)
        cursor = conn.cursor()
        with open(csv_path, newline='', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if header != EXPECTED_COLUMNS:
                raise ValueError(f"Invalid CSV header. Expected {EXPECTED_COLUMNS}, got {header}")
            for line_number, row in enumerate(reader, start=2):
                total += 1
                row_errors = validate_row(row)
                if row_errors:
                    rejected += 1
                    if len(row) != EXPECTED_COLUMN_COUNT:
                        malformed += 1
                    if len(errors) < 20:
                        errors.append({"line": line_number, "errors": row_errors})
                    continue
                cursor.execute(INSERT_SQL, _normalise_row(row))
                if cursor.rowcount:
                    inserted += 1
                else:
                    skipped += 1
        conn.commit()
        result = {
            "total": total, "inserted": inserted, "skipped": skipped,
            "rejected": rejected, "malformed": malformed, "errors": errors,
            "quality_score": round(((total - rejected) / total) * 100, 2) if total else 100.0,
        }
        print(f"Loaded '{csv_path}': {inserted} inserted, {skipped} already present, {rejected} rejected; quality={result['quality_score']:.2f}%")
        log_database_event('load_complete', str(result))
        return result if return_report else inserted
    except Exception as error:
        if conn is not None:
            conn.rollback()
        error_msg = f"Failed to load CSV: {error}"
        log_database_event('load_failed', error_msg, 'error')
        log_system_error('csv_load_error', error_msg, error)
        raise
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    load_csv_into_db()
