"""
generate_data.py
Member 1 (Data Engineer) | Monday deliverable.

Generates realistic synthetic oil-well sensor data (5 wells x 30 days,
FR1) and inserts it into the production_data table in SQLite. Failures
are given physically plausible signatures (low pressure, low oil rate)
so the ML model in train_model.py actually has something to learn.

Run order: db_setup.py must be run first so the table exists.
"""

import random
import datetime
import sqlite3

from config import DB_PATH, WELL_COUNT, DAYS_OF_HISTORY

random.seed(42)  # reproducible data across every run — same seed the guide uses


def generate_rows():
    """Build the list of (Well_ID, Date, Oil_Rate, Water_Cut, Pressure,
    Temperature, Pump_Status) tuples for every well and day."""
    wells = [f'WELL-0{i}' for i in range(1, WELL_COUNT + 1)]
    start_date = datetime.date(2024, 1, 1)
    rows = []

    for well in wells:
        for day in range(DAYS_OF_HISTORY):
            is_failure = random.random() < 0.15  # ~15% failure rate

            pressure = random.uniform(1200, 2800)
            if is_failure:
                pressure *= 0.6  # failures show up as a pressure drop
                oil_rate = random.uniform(50, 120)
            else:
                oil_rate = random.uniform(200, 500)

            rows.append((
                well,
                (start_date + datetime.timedelta(days=day)).isoformat(),
                round(oil_rate, 2),
                round(random.uniform(5, 60), 2),
                round(pressure, 2),
                round(random.uniform(60, 120), 2),
                1 if is_failure else 0,
            ))
    return rows


def insert_rows(rows):
    """Insert generated rows into production_data. Clears any previous
    run first so re-running this script doesn't duplicate data."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM production_data")  # keep re-runs idempotent
    cursor.executemany(
        "INSERT INTO production_data VALUES (?,?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    data_rows = generate_rows()
    insert_rows(data_rows)
    failures = sum(r[-1] for r in data_rows)
    print(f"Inserted {len(data_rows)} rows into {DB_PATH} "
          f"({failures} failure rows, {failures / len(data_rows):.1%})")