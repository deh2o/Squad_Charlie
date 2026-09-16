"""
generate_data.py
Member 1 (Data Engineer) | Monday deliverable.

Step 1 of the data pipeline: generate synthetic oil-well sensor data
(5 wells x 30 days) and write it to CSV. load_csv.py then loads that
CSV into SQLite, and data_loader.py reads back out of the database.
"""

import csv
import datetime
import os
import random

from config import CSV_PATH, WELL_COUNT, DAYS_OF_HISTORY, RAW_DATA_DIR

# Column order here must match the production_data table in db_setup.py,
# because load_csv.py inserts the CSV columns positionally.
CSV_HEADER = [
    "Well_ID", "Date", "Oil_Rate", "Water_Cut",
    "Pressure", "Temperature", "Pump_Status",
]

# Note: Removed fixed seed to allow different data generation each time.
# If reproducible data is needed for testing, set a seed before calling generate_rows()

FAILURE_RATE = 0.15  # roughly 1 reading in 7 is a pump failure


def generate_rows():
    """Build one (Well_ID, Date, ...sensors..., Pump_Status) tuple per well per day."""
    wells = [f'WELL-0{i}' for i in range(1, WELL_COUNT + 1)]
    
    # Use random start date to add variety between datasets
    current_date = datetime.date.today()
    random_days_offset = random.randint(0, 365)  # Random offset up to 1 year
    start_date = current_date - datetime.timedelta(days=random_days_offset + DAYS_OF_HISTORY)
    
    rows = []

    for well in wells:
        for day in range(DAYS_OF_HISTORY):
            # Decide first whether this day is a failure, so the sensor
            # values below can be given a matching physical signature.
            is_failure = random.random() < FAILURE_RATE

            pressure = random.uniform(1200, 2800)
            if is_failure:
                # A failing pump cannot hold pressure or lift fluid, so both
                # drop together. Without this pattern the ML model in
                # train_model.py would have nothing to learn from.
                pressure *= 0.6
                oil_rate = random.uniform(50, 120)
            else:
                oil_rate = random.uniform(200, 500)

            rows.append((
                well,
                # ISO string, not a date object: SQLite stores dates as TEXT.
                (start_date + datetime.timedelta(days=day)).isoformat(),
                round(oil_rate, 2),
                round(random.uniform(5, 60), 2),    # Water_Cut %
                round(pressure, 2),
                round(random.uniform(60, 120), 2),  # Temperature C
                1 if is_failure else 0,             # Pump_Status = the ML target
            ))
    return rows


def get_random_month_year():
    """Generate a unique random month_year filename like 'july_2026.csv'.

    Only generates dates up to the current month/year, not future dates.
    """
    months = [
        'january', 'february', 'march', 'april', 'may', 'june',
        'july', 'august', 'september', 'october', 'november', 'december'
    ]

    # Get current date
    current_date = datetime.datetime.now()
    current_year = current_date.year
    current_month = current_date.month

    # Ensure raw directory exists
    os.makedirs(RAW_DATA_DIR, exist_ok=True)

    # Generate unique filename by checking if it already exists
    max_attempts = 100
    for attempt in range(max_attempts):
        # Random year between 2024 and current year
        year = random.randint(2024, current_year)

        # If it's the current year, only use months up to current month
        if year == current_year:
            month_index = random.randint(0, current_month - 1)
        else:
            # For past years, any month is fine
            month_index = random.randint(0, 11)

        month = months[month_index]
        # Add a random number to make it more unique
        random_suffix = random.randint(1, 999)
        filename = f"{month}_{year}_{random_suffix}.csv"
        csv_path = os.path.join(RAW_DATA_DIR, filename)

        # If file doesn't exist, return it
        if not os.path.exists(csv_path):
            return filename

    # If we couldn't find a unique name, add a timestamp
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    return f"data_{timestamp}.csv"

def export_to_csv(rows, csv_path=CSV_PATH, use_raw_folder=False):
    """Write the generated rows to CSV, creating the folder if needed.

    Args:
        rows: List of data rows to write
        csv_path: Path where to save the CSV (or directory if use_raw_folder=True)
        use_raw_folder: If True, saves to raw/ folder with random month_year name
    """
    if use_raw_folder:
        # Create raw folder and generate random filename
        os.makedirs(RAW_DATA_DIR, exist_ok=True)
        filename = get_random_month_year()
        csv_path = os.path.join(RAW_DATA_DIR, filename)
    else:
        # Ensure directory exists for the given path
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)

    # newline="" stops the csv module writing blank lines between rows on Windows.
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADER)
        writer.writerows(rows)
    print(f"CSV exported: {csv_path}")
    return csv_path


def generate_and_export_csv(use_raw_folder=True):
    """Generate data and export to CSV.

    Args:
        use_raw_folder: If True, saves to raw/ folder with random name.
                        If False, saves to default CSV_PATH.

    Returns:
        Path to the generated CSV file.
    """
    data_rows = generate_rows()
    csv_path = export_to_csv(data_rows, use_raw_folder=use_raw_folder)

    failures = sum(r[-1] for r in data_rows)
    print(f"Generated {len(data_rows)} rows "
          f"({failures} failure rows, {failures / len(data_rows):.1%})")
    return csv_path

if __name__ == "__main__":
    # By default, generate to raw folder with random name
    csv_path = generate_and_export_csv(use_raw_folder=True)
    print(f"CSV file created at: {csv_path}")
    print("Run 'python load_csv.py' to load this data into the database.")
