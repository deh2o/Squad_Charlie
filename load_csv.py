import csv
import sqlite3
from config import DB_PATH, csv_path

# data/production_dat.csv
# C:\Users\idams\OneDrive\Desktop\works\GitHub\squad_charlie\production_data.csv

def load_csv_into_db(csv_path):
    """Load new CSV rows into production_data without deleting existing data."""

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    with open(csv_path, newline='') as f:
        reader = csv.reader(f)
        header = next(reader)  # skip header row

        for row in reader:
            # Safety: ensure row has exactly 7 columns
            if len(row) != 7:
                print(f"Skipping malformed row: {row}")
                continue

            try:
                cursor.execute("""
                    INSERT INTO production_data
                    (Well_ID, Date, Oil_Rate, Water_Cut, Pressure, Temperature, Pump_Status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, row)
            except sqlite3.IntegrityError as e:
                print(f"Skipping duplicate or invalid row {row}: {e}")
            except Exception as e:
                print(f"Error inserting row {row}: {e}")

    conn.commit()
    conn.close()
    print(f"CSV '{csv_path}' successfully loaded into {DB_PATH}")
